"""Safe browser fallback that feeds rendered DOM into the deterministic parser."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

from app.schemas.collector import CollectorFailure, FetchStatus, SourceFetchResult, SourceRegistration
from app.services.collectors.browser_renderer import BrowserRenderer, BrowserUnavailable
from app.services.collectors.html_extractor import extract_product, extract_visible_text
from app.services.collectors.preflight import validate_registered_url


class BrowserProductPageCollector:
    def __init__(self, *, renderer: BrowserRenderer, max_bytes: int, max_content_chars: int, resolver) -> None:
        self.renderer = renderer
        self.max_bytes = max_bytes
        self.max_content_chars = max_content_chars
        self.resolver = resolver

    async def fetch(self, url: str, source: SourceRegistration) -> SourceFetchResult:
        try:
            rendered = await self.renderer.render(url)
        except BrowserUnavailable as exc:
            return self._failure(url, source, FetchStatus.BROWSER_UNAVAILABLE, str(exc))
        except (TimeoutError, RuntimeError, OSError) as exc:
            return self._failure(
                url, source, FetchStatus.FETCH_ERROR,
                f"Browser rendering failed ({type(exc).__name__}).",
            )

        try:
            final_url = validate_registered_url(
                rendered.final_url, source, resolver=self.resolver
            )
        except ValueError as exc:
            return self._failure(url, source, FetchStatus.INVALID_URL, str(exc))
        if len(rendered.html.encode("utf-8")) > self.max_bytes:
            return self._failure(
                final_url, source, FetchStatus.FETCH_ERROR,
                "Rendered product page exceeds configured byte limit.",
            )
        lowered = rendered.html.lower()
        if "captcha" in lowered or "verify you are human" in lowered:
            return self._failure(
                final_url, source, FetchStatus.ACCESS_RESTRICTED,
                "Human verification encountered; rendering stopped.",
            )

        observation = extract_product(
            rendered.html,
            url=final_url,
            platform=source.source_id,
            default_currency=source.default_currency,
            currency_minor_unit=source.currency_minor_unit,
        )
        if observation is None or not any(
            evidence.evidence_type == "JSON_LD" and evidence.field == "name"
            for evidence in observation.evidence
        ):
            return self._failure(
                final_url, source, FetchStatus.NOT_PRODUCT_PAGE,
                "Rendered DOM contains no JSON-LD Product identity.",
            )

        warnings: list[str] = []
        verified_offers = []
        for offer in observation.offers:
            try:
                offer.product_url = validate_registered_url(
                    urljoin(final_url, offer.product_url), source, resolver=self.resolver
                )
            except ValueError:
                warnings.append("Rendered offer outside the approved source host was omitted.")
                continue
            verified_offers.append(offer)
        observation.offers = verified_offers
        if observation.image_url:
            try:
                observation.image_url = validate_registered_url(
                    urljoin(final_url, observation.image_url), source, resolver=self.resolver
                )
            except ValueError:
                observation.image_url = None
                warnings.append("Rendered image outside the approved source host was omitted.")

        exact_offer = any(
            any(item.field == "sale_price" and item.verification_status == "VERIFIED" for item in offer.evidence)
            and any(item.field == "sku" for item in offer.evidence)
            for offer in observation.offers
        )
        now = datetime.now(timezone.utc)
        if not exact_offer:
            warnings.append("Rendered product found; exact currency-qualified price and SKU were not both verified.")
        return SourceFetchResult(
            status=FetchStatus.SUCCESS if exact_offer else FetchStatus.PARTIAL_DATA,
            source_url=final_url,
            source_domain=source.domain,
            platform=source.source_id,
            fetched_at=now,
            content_type="text/html; rendered=crawl4ai",
            content_text=extract_visible_text(rendered.html, max_chars=self.max_content_chars),
            observation=observation,
            warnings=warnings,
        )

    @staticmethod
    def _failure(url: str, source: SourceRegistration, status: FetchStatus, message: str) -> SourceFetchResult:
        return SourceFetchResult(
            status=status,
            source_url=url,
            source_domain=source.domain,
            platform=source.source_id,
            failure=CollectorFailure(code=status, message=message),
        )
