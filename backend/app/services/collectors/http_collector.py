"""Bounded HTTP collector with redirect, content and access-control semantics."""

from __future__ import annotations

import asyncio
import socket
import time
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx

from app.schemas.collector import CollectorFailure, FetchStatus, SourceFetchResult
from app.services.collectors.html_extractor import extract_product
from app.services.collectors.network_policy import build_pinned_http_client
from app.services.collectors.url_safety import ALLOWED_HOSTS, UnsafeURL, validate_marketplace_url


class HTTPMarketplaceCollector:
    MAX_BYTES = 2_000_000
    MAX_REDIRECTS = 3
    _semaphores: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))
    _rate_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    _last_request: dict[str, float] = defaultdict(float)

    def __init__(self, platform: str, *, client: httpx.AsyncClient | None = None,
                 resolve_dns: bool = True, timeout: float = 8.0,
                 resolver=socket.getaddrinfo) -> None:
        self.platform = platform
        self._client = client
        self.resolve_dns = resolve_dns
        self.timeout = timeout
        self.resolver = resolver
        self._restricted_failures: dict[str, int] = defaultdict(int)

    def _failure(self, url: str, status: FetchStatus, message: str, *, http_status: int | None = None,
                 retryable: bool = False) -> SourceFetchResult:
        return SourceFetchResult(status=status, source_url=url, platform=self.platform,
            http_status=http_status, failure=CollectorFailure(code=status, message=message,
            http_status=http_status, retryable=retryable))

    async def _read_limited(self, client: httpx.AsyncClient, url: str) -> tuple[int, httpx.Headers, bytes]:
        """Stream at most MAX_BYTES so a hostile Content-Length cannot exhaust memory."""
        async with client.stream("GET", url) as response:
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > self.MAX_BYTES:
                raise ValueError("Response body exceeds safety limit")
            if response.status_code in {301, 302, 303, 307, 308}:
                return response.status_code, response.headers, b""
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.MAX_BYTES:
                    raise ValueError("Response body exceeds safety limit")
                chunks.append(chunk)
            return response.status_code, response.headers, b"".join(chunks)

    async def fetch(self, url: str) -> SourceFetchResult:
        try:
            validated = validate_marketplace_url(url, resolve_dns=self.resolve_dns, resolver=self.resolver)
        except UnsafeURL as exc:
            return self._failure(url, FetchStatus.INVALID_URL, str(exc))
        if validated.platform != self.platform:
            return self._failure(url, FetchStatus.INVALID_URL, "URL belongs to another platform")
        if self._restricted_failures[validated.host] >= 3:
            return self._failure(validated.url, FetchStatus.ACCESS_RESTRICTED, "Circuit breaker is open")

        owned = self._client is None
        client = self._client or build_pinned_http_client(
            allowed_domains=ALLOWED_HOSTS[self.platform],
            allow_subdomains=True,
            resolver=self.resolver,
            timeout=self.timeout,
            headers={"User-Agent": "SmartShoppingResearch/1.0 (+local educational project)"},
        )
        current = validated.url
        try:
            async with self._semaphores[validated.host]:
                for _ in range(self.MAX_REDIRECTS + 1):
                    async with self._rate_locks[validated.host]:
                        delay = .1 - (time.monotonic() - self._last_request[validated.host])
                        if delay > 0:
                            await asyncio.sleep(delay)
                        self._last_request[validated.host] = time.monotonic()
                    status_code, headers, body = await self._read_limited(client, current)
                    if status_code in {301, 302, 303, 307, 308}:
                        location = headers.get("location")
                        if not location:
                            return self._failure(current, FetchStatus.PROVIDER_FAILED, "Redirect has no location", http_status=status_code)
                        redirected = urljoin(current, location)
                        try:
                            checked = validate_marketplace_url(redirected, resolve_dns=self.resolve_dns, resolver=self.resolver)
                        except UnsafeURL:
                            return self._failure(current, FetchStatus.INVALID_URL, "Redirect target is unsafe", http_status=status_code)
                        if checked.platform != self.platform:
                            return self._failure(current, FetchStatus.INVALID_URL, "Cross-platform redirect is not allowed", http_status=status_code)
                        current = checked.url
                        continue
                    break
                else:
                    return self._failure(current, FetchStatus.PROVIDER_FAILED, "Too many redirects")

            if status_code in {401, 403, 429}:
                self._restricted_failures[validated.host] += 1
                return self._failure(current, FetchStatus.ACCESS_RESTRICTED, "Marketplace restricted automated access",
                    http_status=status_code, retryable=status_code == 429)
            if status_code >= 400:
                return self._failure(current, FetchStatus.PROVIDER_FAILED, "Marketplace request failed",
                    http_status=status_code, retryable=status_code >= 500)
            content_type = headers.get("content-type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return self._failure(current, FetchStatus.NOT_PRODUCT_PAGE, "Unsupported content type", http_status=status_code)
            html = body.decode("utf-8", errors="replace")
            lowered = html.lower()
            if "captcha" in lowered or "verify you are human" in lowered:
                self._restricted_failures[validated.host] += 1
                return self._failure(current, FetchStatus.ACCESS_RESTRICTED, "CAPTCHA or human verification encountered", http_status=status_code)
            observation = extract_product(html, url=current, platform=self.platform)
            if observation is None:
                return self._failure(current, FetchStatus.NOT_PRODUCT_PAGE, "No product identity on page", http_status=status_code)
            status = FetchStatus.SUCCESS if observation.offers else FetchStatus.PARTIAL_DATA
            warnings = [] if observation.offers else ["Product identity found but no offer price was verified."]
            return SourceFetchResult(status=status, source_url=current, platform=self.platform,
                fetched_at=datetime.now(timezone.utc), http_status=status_code,
                content_type=content_type, observation=observation, warnings=warnings)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return self._failure(current, FetchStatus.PROVIDER_FAILED, type(exc).__name__, retryable=True)
        except ValueError as exc:
            return self._failure(current, FetchStatus.PROVIDER_FAILED, str(exc))
        finally:
            if owned:
                await client.aclose()
