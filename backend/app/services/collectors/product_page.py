"""Public, registered product-page fetcher using HTTPX and deterministic JSON-LD."""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx

from app.schemas.collector import (
    CollectorFailure,
    FetchStatus,
    SourceFetchResult,
    SourceRegistration,
)
from app.services.collectors.html_extractor import (
    extract_product,
    extract_visible_text,
)
from app.services.collectors.preflight import (
    USER_AGENT,
    host_request,
    preflight_source,
    record_retry_after,
    validate_registered_url,
)


def looks_javascript_dependent(html: str) -> bool:
    """Return true only for common empty application shells needing rendering."""
    lowered = html.lower()
    markers = (
        'id="__next"', "id='__next'", "__next_data__",
        'id="root"', "id='root'", 'id="app"', "id='app'",
    )
    visible = extract_visible_text(html, max_chars=500)
    return any(marker in lowered for marker in markers) and len(visible) < 120


class RegisteredProductPageCollector:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        max_bytes: int = 2_000_000,
        min_interval_seconds: float = 0.0,
        max_content_chars: int = 12000,
        resolver=None,
    ) -> None:
        self.client = client
        self.max_bytes = max_bytes
        self.min_interval_seconds = min_interval_seconds
        self.max_content_chars = max_content_chars
        self.resolver = resolver

    async def fetch(self, url: str, source: SourceRegistration) -> SourceFetchResult:
        current = url
        for _ in range(4):
            preflight = await preflight_source(
                current,
                source,
                self.client,
                resolver=self.resolver or socket.getaddrinfo,
                min_interval_seconds=self.min_interval_seconds,
            )
            if not preflight.allowed:
                return self._failure(
                    current,
                    source,
                    preflight.status or FetchStatus.SOURCE_NOT_PERMITTED,
                    preflight.message or "Source preflight failed.",
                    robots_checked_at=preflight.robots_checked_at,
                )
            current = preflight.canonical_url or current
            try:
                async with host_request(
                    urlsplit(current).hostname or "",
                    self.min_interval_seconds,
                ):
                    async with self.client.stream(
                        "GET",
                        current,
                        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                return self._failure(
                                    current, source, FetchStatus.FETCH_ERROR,
                                    "Redirect has no Location.",
                                    robots_checked_at=preflight.robots_checked_at,
                                )
                            try:
                                target = validate_registered_url(
                                    urljoin(current, location),
                                    source,
                                    resolver=self.resolver or socket.getaddrinfo,
                                )
                            except ValueError as exc:
                                return self._failure(
                                    current, source, FetchStatus.INVALID_URL, str(exc),
                                    robots_checked_at=preflight.robots_checked_at,
                                )
                            if target == current:
                                return self._failure(
                                    current, source, FetchStatus.FETCH_ERROR,
                                    "Redirect loop.",
                                    robots_checked_at=preflight.robots_checked_at,
                                )
                            current = target
                            continue
                        status = response.status_code
                        content_type = response.headers.get("content-type", "").lower()
                        if status in {401, 403, 429}:
                            retry_after = (
                                record_retry_after(
                                    urlsplit(current).hostname or "",
                                    response.headers.get("retry-after"),
                                )
                                if status == 429
                                else None
                            )
                            return self._failure(
                                current,
                                source,
                                FetchStatus.ACCESS_RESTRICTED,
                                f"Product page access restricted (HTTP {status}).",
                                http_status=status,
                                robots_checked_at=preflight.robots_checked_at,
                                retry_after_seconds=retry_after,
                            )
                        if status >= 400:
                            return self._failure(
                                current, source, FetchStatus.FETCH_ERROR,
                                f"Product page request failed (HTTP {status}).",
                                http_status=status,
                                robots_checked_at=preflight.robots_checked_at,
                            )
                        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                            return self._failure(
                                current, source, FetchStatus.NOT_PRODUCT_PAGE,
                                "Response is not an HTML product page.", http_status=status,
                                robots_checked_at=preflight.robots_checked_at,
                            )
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > self.max_bytes:
                                return self._failure(
                                    current, source, FetchStatus.FETCH_ERROR,
                                    "Product page exceeds configured byte limit.", http_status=status,
                                    robots_checked_at=preflight.robots_checked_at,
                                )
                html = bytes(body).decode("utf-8", errors="replace")
                lowered = html.lower()
                if "captcha" in lowered or "verify you are human" in lowered:
                    return self._failure(
                        current, source, FetchStatus.ACCESS_RESTRICTED,
                        "Human verification encountered; browser fallback is not allowed.",
                        http_status=status,
                        robots_checked_at=preflight.robots_checked_at,
                    )
                observation = extract_product(
                    html,
                    url=current,
                    platform=source.source_id,
                    default_currency=source.default_currency,
                    currency_minor_unit=source.currency_minor_unit,
                )
                if observation is None or not any(
                    evidence.evidence_type == "JSON_LD" and evidence.field == "name"
                    for evidence in observation.evidence
                ):
                    result = self._failure(
                        current, source, FetchStatus.NOT_PRODUCT_PAGE,
                        "No JSON-LD Product identity was found.", http_status=status,
                        robots_checked_at=preflight.robots_checked_at,
                    )
                    result.content_text = extract_visible_text(
                        html, max_chars=self.max_content_chars
                    )
                    if looks_javascript_dependent(html):
                        result.warnings.append("JS_RENDERING_CANDIDATE")
                    return result
                warnings = []
                verified_offers = []
                for offer in observation.offers:
                    try:
                        offer.product_url = validate_registered_url(
                            urljoin(current, offer.product_url),
                            source,
                            resolver=self.resolver or socket.getaddrinfo,
                        )
                    except ValueError:
                        warnings.append(
                            "Offer was omitted because its URL is outside the approved source host."
                        )
                        continue
                    verified_offers.append(offer)
                observation.offers = verified_offers
                if observation.image_url:
                    try:
                        observation.image_url = validate_registered_url(
                            observation.image_url,
                            source,
                            resolver=self.resolver or socket.getaddrinfo,
                        )
                    except ValueError:
                        observation.image_url = None
                        warnings.append(
                            "Image URL was omitted because it is outside the approved source host."
                        )
                offer_verified = any(
                    offer.evidence
                    and any(
                        item.field == "sale_price" and item.verification_status == "VERIFIED"
                        for item in offer.evidence
                    )
                    and any(item.field == "sku" for item in offer.evidence)
                    for offer in observation.offers
                )
                observed_at = datetime.now(timezone.utc)
                return SourceFetchResult(
                    status=FetchStatus.SUCCESS if offer_verified else FetchStatus.PARTIAL_DATA,
                    source_url=current,
                    source_domain=urlsplit(current).hostname,
                    platform=source.source_id,
                    fetched_at=observed_at,
                    robots_checked_at=preflight.robots_checked_at,
                    http_status=status,
                    content_type=content_type,
                    content_text=extract_visible_text(
                        html, max_chars=self.max_content_chars
                    ),
                    observation=observation,
                    warnings=warnings + (
                        []
                        if offer_verified
                        else ["Product page found; no exact currency-qualified price and SKU were verified."]
                    ),
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                return self._failure(
                    current,
                    source,
                    FetchStatus.FETCH_ERROR,
                    f"Product page request failed ({type(exc).__name__}).",
                    robots_checked_at=preflight.robots_checked_at,
                )
        return self._failure(
            current, source, FetchStatus.FETCH_ERROR,
            "Too many same-host redirects.",
            robots_checked_at=preflight.robots_checked_at,
        )

    @staticmethod
    def _failure(
        url: str,
        source: SourceRegistration,
        status: FetchStatus,
        message: str,
        *,
        http_status: int | None = None,
        robots_checked_at: datetime | None = None,
        retry_after_seconds: float | None = None,
    ) -> SourceFetchResult:
        return SourceFetchResult(
            status=status,
            source_url=url,
            source_domain=source.domain,
            platform=source.source_id,
            http_status=http_status,
            robots_checked_at=robots_checked_at,
            failure=CollectorFailure(
                code=status,
                message=message,
                http_status=http_status,
                retry_after_seconds=retry_after_seconds,
            ),
        )
