"""Merchant permission, URL, DNS and robots preflight for generic sources."""

from __future__ import annotations

import asyncio
import socket
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.schemas.collector import FetchStatus, SourceRegistration
from app.services.collectors.network_policy import resolve_public_addresses


USER_AGENT = "SmartShoppingResearch/1.0 (+educational product comparison)"
MAX_ROBOTS_BYTES = 1_000_000
ROBOTS_CACHE_TTL_SECONDS = 300
_HOST_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_HOST_SEMAPHORES: dict[tuple[int, str], asyncio.Semaphore] = {}
_LAST_REQUEST: dict[str, float] = {}
_BLOCKED_UNTIL: dict[str, float] = {}
_ROBOTS_CACHE: dict[
    str, tuple[float, datetime, RobotFileParser | None]
] = {}


async def pace_host(host: str, min_interval_seconds: float) -> None:
    """Serialize request starts and enforce a conservative per-host interval."""
    now = time.monotonic()
    if (
        min_interval_seconds <= 0
        and _BLOCKED_UNTIL.get(host, 0) <= now
    ):
        return
    lock = _HOST_LOCKS.setdefault(
        (id(asyncio.get_running_loop()), host), asyncio.Lock()
    )
    async with lock:
        now = time.monotonic()
        delay = max(
            max(0.0, min_interval_seconds - (now - _LAST_REQUEST.get(host, 0))),
            _BLOCKED_UNTIL.get(host, 0) - now,
        )
        if delay > 0:
            await asyncio.sleep(delay)
        _LAST_REQUEST[host] = time.monotonic()


def record_retry_after(host: str, value: str | None) -> float | None:
    if not value:
        return None
    now = time.monotonic()
    try:
        delay = max(0.0, float(value.strip()))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            delay = max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
    _BLOCKED_UNTIL[host] = max(_BLOCKED_UNTIL.get(host, 0), now + delay)
    return delay


@asynccontextmanager
async def host_request(host: str, min_interval_seconds: float = 0.0):
    """Hold the single per-host request slot while enforcing start pacing."""
    semaphore = _HOST_SEMAPHORES.setdefault(
        (id(asyncio.get_running_loop()), host), asyncio.Semaphore(1)
    )
    await semaphore.acquire()
    try:
        await pace_host(host, min_interval_seconds)
        yield
    finally:
        semaphore.release()


@dataclass(frozen=True, slots=True)
class PreflightResult:
    allowed: bool
    status: FetchStatus | None = None
    message: str | None = None
    checked_at: datetime = datetime.min.replace(tzinfo=timezone.utc)
    canonical_url: str | None = None
    robots_checked_at: datetime | None = None


def validate_registered_url(
    url: str,
    source: SourceRegistration,
    *,
    resolver=socket.getaddrinfo,
) -> str:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Malformed URL") from exc
    host = (parsed.hostname or "").rstrip(".").lower()
    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or not host.isascii()
    ):
        raise ValueError("Only credential-free HTTPS URLs on the default port are permitted")
    exact = host == source.domain
    subdomain = source.allow_subdomains and host.endswith("." + source.domain)
    if not (exact or subdomain):
        raise ValueError("URL host is not registered for this source")
    decoded_path = unquote(parsed.path or "/")
    if "\\" in decoded_path or any(
        segment in {".", ".."} for segment in decoded_path.split("/")
    ):
        raise ValueError("URL path is not normalized")
    if not any(
        decoded_path == prefix.rstrip("/") or decoded_path.startswith(prefix.rstrip("/") + "/")
        for prefix in source.allowed_paths
    ):
        raise ValueError("URL path is not registered for this source")
    try:
        resolve_public_addresses(host, 443, resolver=resolver)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


async def preflight_source(
    url: str,
    source: SourceRegistration,
    client: httpx.AsyncClient,
    *,
    resolver=socket.getaddrinfo,
    min_interval_seconds: float = 0.0,
) -> PreflightResult:
    checked_at = datetime.now(timezone.utc)
    if not source.enabled or source.permission_status != "approved" or not source.permission_basis:
        return PreflightResult(
            False,
            FetchStatus.SOURCE_NOT_PERMITTED,
            "Source is not explicitly approved in the source registry.",
            checked_at,
        )
    if source.terms_checked_at is None:
        return PreflightResult(
            False,
            FetchStatus.SOURCE_NOT_PERMITTED,
            "Terms review date is missing; source access is fail-closed.",
            checked_at,
        )
    try:
        canonical_url = validate_registered_url(url, source, resolver=resolver)
    except ValueError as exc:
        return PreflightResult(False, FetchStatus.INVALID_URL, str(exc), checked_at)

    parsed = urlsplit(canonical_url)
    robots_url = source.robots_url or f"https://{parsed.netloc}/robots.txt"
    try:
        robots = urlsplit(robots_url)
        robots_port = robots.port
        if (
            robots.scheme != "https"
            or robots.hostname != parsed.hostname
            or robots.username is not None
            or robots.password is not None
            or robots_port not in {None, 443}
            or robots.path != "/robots.txt"
            or robots.query
            or robots.fragment
        ):
            return PreflightResult(
                False,
                FetchStatus.SOURCE_NOT_PERMITTED,
                "Configured robots URL must be this host's HTTPS /robots.txt.",
                checked_at,
            )
        cached = _ROBOTS_CACHE.get(robots_url)
        if cached is not None and time.monotonic() - cached[0] < ROBOTS_CACHE_TTL_SECONDS:
            checked_at = cached[1]
            parser = cached[2]
            if parser is None or parser.can_fetch(USER_AGENT, canonical_url):
                return PreflightResult(True, checked_at=checked_at,
                    canonical_url=canonical_url, robots_checked_at=checked_at)
            return PreflightResult(
                False,
                FetchStatus.ROBOTS_DISALLOWED,
                "robots.txt disallows this URL for the collector user agent.",
                checked_at,
                robots_checked_at=checked_at,
            )
        async with host_request(parsed.hostname or "", min_interval_seconds):
            async with client.stream(
                "GET", robots_url, headers={"User-Agent": USER_AGENT}
            ) as response:
                if response.status_code in {404, 410}:
                    _ROBOTS_CACHE[robots_url] = (
                        time.monotonic(), checked_at, None
                    )
                    return PreflightResult(
                        True, checked_at=checked_at, canonical_url=canonical_url,
                        robots_checked_at=checked_at,
                    )
                if response.status_code == 429:
                    record_retry_after(
                        parsed.hostname or "",
                        response.headers.get("retry-after"),
                    )
                    return PreflightResult(
                        False,
                        FetchStatus.ACCESS_RESTRICTED,
                        "robots.txt request was rate limited; stop and retry only later.",
                        checked_at,
                        robots_checked_at=checked_at,
                    )
                if response.status_code != 200:
                    return PreflightResult(
                        False,
                        FetchStatus.SOURCE_NOT_PERMITTED,
                        f"robots.txt could not be verified (HTTP {response.status_code}).",
                        checked_at,
                        robots_checked_at=checked_at,
                    )
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_ROBOTS_BYTES:
                        return PreflightResult(
                            False,
                            FetchStatus.SOURCE_NOT_PERMITTED,
                            "robots.txt exceeds the safety size limit.",
                            checked_at,
                            robots_checked_at=checked_at,
                        )
        robots_text = bytes(content).decode("utf-8", errors="replace")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(robots_text.splitlines())
        _ROBOTS_CACHE[robots_url] = (time.monotonic(), checked_at, parser)
        if not parser.can_fetch(USER_AGENT, canonical_url):
            return PreflightResult(
                False,
                FetchStatus.ROBOTS_DISALLOWED,
                "robots.txt disallows this URL for the collector user agent.",
                checked_at,
                robots_checked_at=checked_at,
            )
        return PreflightResult(
            True, checked_at=checked_at, canonical_url=canonical_url,
            robots_checked_at=checked_at,
        )
    except ValueError:
        return PreflightResult(
            False,
            FetchStatus.SOURCE_NOT_PERMITTED,
            "Configured robots URL is malformed or unsafe.",
            checked_at,
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        return PreflightResult(
            False,
            FetchStatus.SOURCE_NOT_PERMITTED,
            f"robots.txt could not be verified ({type(exc).__name__}); access is fail-closed.",
            checked_at,
            robots_checked_at=checked_at,
        )
