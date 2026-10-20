"""Bounded WooCommerce Store API adapter for explicitly registered stores."""

from __future__ import annotations

import json
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

from app.schemas.collector import (
    CollectorFailure,
    CollectorSearchResult,
    FetchStatus,
    FieldEvidence,
    OfferObservation,
    ProductObservation,
    SourceFetchResult,
    SourceRegistration,
    VariantIdentity,
)
from app.services.collectors.preflight import (
    USER_AGENT,
    host_request,
    preflight_source,
    record_retry_after,
    validate_registered_url,
)


class WooCommerceStoreAPICollector:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        max_bytes: int = 2_000_000,
        max_pages: int = 2,
        min_interval_seconds: float = 1.0,
        resolver=None,
    ) -> None:
        self.client = client
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.min_interval_seconds = min_interval_seconds
        self.resolver = resolver

    async def search(
        self,
        source: SourceRegistration,
        query: str,
        *,
        max_products: int = 5,
    ) -> CollectorSearchResult:
        attempted_at = datetime.now(timezone.utc)
        bounded_products = max(1, min(max_products, source.max_products, 50))
        bounded_pages = max(1, min(self.max_pages, source.max_pages, 5))
        base = f"https://{source.domain}{source.api_path}"
        resolver = self.resolver or socket.getaddrinfo
        preflight = await preflight_source(
            base,
            source,
            self.client,
            resolver=resolver,
            min_interval_seconds=self.min_interval_seconds,
        )
        if not preflight.allowed:
            status = preflight.status or FetchStatus.SOURCE_NOT_PERMITTED
            return CollectorSearchResult(
                source_id=source.source_id,
                query=query,
                status=status,
                fetched_at=attempted_at,
                robots_checked_at=preflight.robots_checked_at,
                failure=CollectorFailure(code=status, message=preflight.message or status.value),
            )

        products: list[SourceFetchResult] = []
        warnings: list[str] = []
        seen_product_ids: set[str] = set()
        per_page = min(bounded_products, 20)
        try:
            for page in range(1, bounded_pages + 1):
                if len(products) >= bounded_products:
                    break
                async with host_request(source.domain, self.min_interval_seconds):
                    async with self.client.stream(
                        "GET",
                        base,
                        params={"search": query[:200], "page": page, "per_page": per_page},
                        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                    ) as response:
                        if response.status_code in {401, 403, 429}:
                            retry_after = (
                                record_retry_after(
                                    source.domain,
                                    response.headers.get("retry-after"),
                                )
                                if response.status_code == 429
                                else None
                            )
                            return self._failed(
                                source,
                                query,
                                FetchStatus.ACCESS_RESTRICTED,
                                f"Store API access restricted (HTTP {response.status_code}).",
                                response.status_code,
                                retryable=response.status_code == 429,
                                robots_checked_at=preflight.robots_checked_at,
                                retry_after_seconds=retry_after,
                            )
                        if response.status_code >= 400:
                            status = FetchStatus.FETCH_ERROR
                            return self._failed(
                                source,
                                query,
                                status,
                                f"Store API request failed (HTTP {response.status_code}).",
                                response.status_code,
                                retryable=response.status_code >= 500,
                                robots_checked_at=preflight.robots_checked_at,
                            )
                        content_type = response.headers.get("content-type", "").lower()
                        if "application/json" not in content_type:
                            return self._failed(
                                source, query, FetchStatus.FETCH_ERROR,
                                "Store API returned a non-JSON response.",
                                robots_checked_at=preflight.robots_checked_at,
                            )
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > self.max_bytes:
                                return self._failed(
                                    source, query, FetchStatus.FETCH_ERROR,
                                    "Store API response exceeds byte limit.",
                                    robots_checked_at=preflight.robots_checked_at,
                                )
                try:
                    payload = json.loads(content)
                except (ValueError, UnicodeDecodeError):
                    return self._failed(
                        source, query, FetchStatus.FETCH_ERROR,
                        "Store API returned malformed JSON.",
                        robots_checked_at=preflight.robots_checked_at,
                    )
                if not isinstance(payload, list):
                    return self._failed(
                        source, query, FetchStatus.FETCH_ERROR,
                        "Store API product collection is not an array.",
                        robots_checked_at=preflight.robots_checked_at,
                    )
                for item in payload:
                    if len(products) >= bounded_products:
                        break
                    if not isinstance(item, dict):
                        warnings.append("Skipped a non-object product record.")
                        continue
                    product_id = item.get("id")
                    if product_id is not None:
                        product_id = str(product_id)
                        if product_id in seen_product_ids:
                            warnings.append(
                                f"Skipped duplicate source product ID {product_id}."
                            )
                            continue
                    try:
                        product_result = self._product_result(
                            item, source, base, preflight.robots_checked_at
                        )
                        if product_id is not None:
                            seen_product_ids.add(product_id)
                        products.append(product_result)
                        if product_result.status == FetchStatus.PARTIAL_DATA:
                            warnings.append(
                                f"Product {len(products)} has no exact currency-qualified SKU price."
                            )
                    except (KeyError, TypeError, ValueError) as exc:
                        warnings.append(f"Skipped an invalid product record: {type(exc).__name__}.")
                if len(payload) < per_page:
                    break
            return CollectorSearchResult(
                source_id=source.source_id,
                query=query,
                status=FetchStatus.PARTIAL_DATA if warnings else FetchStatus.SUCCESS,
                fetched_at=attempted_at,
                robots_checked_at=preflight.robots_checked_at,
                products=products,
                warnings=warnings,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return self._failed(
                source,
                query,
                FetchStatus.FETCH_ERROR,
                f"Store API request failed ({type(exc).__name__}).",
                retryable=True,
                robots_checked_at=preflight.robots_checked_at,
            )

    @staticmethod
    def _failed(
        source: SourceRegistration,
        query: str,
        status: FetchStatus,
        message: str,
        http_status: int | None = None,
        *,
        retryable: bool = False,
        robots_checked_at: datetime | None = None,
        retry_after_seconds: float | None = None,
    ) -> CollectorSearchResult:
        return CollectorSearchResult(
            source_id=source.source_id,
            query=query,
            status=status,
            failure=CollectorFailure(
                code=status,
                message=message,
                retryable=retryable,
                http_status=http_status,
                retry_after_seconds=retry_after_seconds,
            ),
            robots_checked_at=robots_checked_at,
        )

    def _product_result(
        self,
        raw: dict,
        source: SourceRegistration,
        api_url: str,
        robots_checked_at: datetime | None,
    ) -> SourceFetchResult:
        product_id = raw.get("id")
        name = raw.get("name")
        permalink = raw.get("permalink")
        if product_id is None or not isinstance(name, str) or not name.strip():
            raise ValueError("missing product identity")
        if not isinstance(permalink, str) or not permalink.strip():
            raise ValueError("missing product URL")
        product_url = validate_registered_url(
            permalink,
            source,
            resolver=self.resolver or socket.getaddrinfo,
        )

        prices = raw.get("prices")
        if not isinstance(prices, dict):
            prices = {}
        currency = prices.get("currency_code") or source.default_currency
        minor_unit = prices.get("currency_minor_unit")
        if minor_unit is None:
            minor_unit = source.currency_minor_unit
        if isinstance(minor_unit, bool) or not isinstance(minor_unit, int) or not 0 <= minor_unit <= 4:
            minor_unit = None
        current_units = _integer_units(prices.get("price"))
        regular_units = _integer_units(prices.get("regular_price"))
        currency_code = str(currency).upper() if isinstance(currency, str) and currency else "UNK"
        exact_current = current_units is not None and minor_unit is not None and currency_code != "UNK"
        integral_currency = exact_current and minor_unit == 0
        product_type = str(raw.get("type") or "simple").lower()
        raw_sku = raw.get("sku")
        sku = (
            str(raw_sku).strip()
            if product_type != "variable"
            and isinstance(raw_sku, (str, int))
            and str(raw_sku).strip()
            else None
        )
        if product_type == "variable":
            exact_current = False
            integral_currency = False

        observed_at = datetime.now(timezone.utc)
        evidence = [
            FieldEvidence(
                field="name",
                value=name.strip(),
                source_url=api_url,
                json_path="name",
                evidence_type="PUBLIC_API",
                observed_at=observed_at,
                verification_status="VERIFIED",
            )
        ]
        offer_evidence: list[FieldEvidence] = []
        if exact_current:
            offer_evidence.append(
                FieldEvidence(
                    field="price",
                    value={
                        "minor_units": current_units,
                        "currency": currency_code,
                        "currency_minor_unit": minor_unit,
                        "json_path": "prices.price",
                    },
                    source_url=api_url,
                    json_path="prices.price",
                    evidence_type="PUBLIC_API",
                    observed_at=observed_at,
                    verification_status="VERIFIED",
                )
            )
        if sku:
            offer_evidence.append(
                FieldEvidence(
                    field="sku",
                    value=sku,
                    source_url=api_url,
                    json_path="sku",
                    evidence_type="PUBLIC_API",
                    observed_at=observed_at,
                    verification_status="VERIFIED",
                )
            )
        image_url = None
        images = raw.get("images")
        if isinstance(images, list) and images and isinstance(images[0], dict):
            candidate_image = images[0].get("src")
            if isinstance(candidate_image, str) and candidate_image.startswith("https://"):
                try:
                    image_url = validate_registered_url(
                        candidate_image,
                        source,
                        resolver=self.resolver or socket.getaddrinfo,
                    )
                except ValueError:
                    image_url = None

        offer = OfferObservation(
            identity=VariantIdentity(
                platform=source.source_id,
                external_product_id=str(product_id),
                external_sku_id=sku,
            ),
            merchant=source.domain,
            listed_price=regular_units if exact_current and minor_unit == 0 else None,
            sale_price=current_units if integral_currency else None,
            listed_price_minor_units=regular_units if exact_current else None,
            sale_price_minor_units=current_units if exact_current else None,
            currency_minor_unit=minor_unit,
            currency=currency_code,
            availability="in_stock" if raw.get("is_in_stock") is True else (
                "out_of_stock" if raw.get("is_in_stock") is False else None
            ),
            product_url=product_url,
            observed_at=observed_at,
            evidence=offer_evidence,
        )
        observation = ProductObservation(
            name=name.strip(),
            brand=_brand(raw.get("brands")),
            category=_category(raw.get("categories")),
            image_url=image_url,
            offers=[offer],
            evidence=evidence,
        )
        status = (
            FetchStatus.SUCCESS
            if exact_current and sku is not None
            else FetchStatus.PARTIAL_DATA
        )
        warnings = []
        if not exact_current:
            warnings.append(
                "No exact currency-qualified price was returned."
                if product_type != "variable"
                else "Variable product price needs a selected variation; no SKU-level offer was recorded."
            )
        elif sku is None:
            warnings.append("SKU is missing; source product ID remains the only product identifier.")
        return SourceFetchResult(
            status=status,
            source_url=product_url,
            platform=source.source_id,
            source_domain=source.domain,
            fetched_at=observed_at,
            robots_checked_at=robots_checked_at,
            http_status=200,
            content_type="application/json",
            observation=observation,
            warnings=warnings,
        )


def _integer_units(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value.strip())
    return None


def _brand(value: object) -> str | None:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict) and isinstance(first.get("name"), str):
            return first["name"].strip() or None
        if isinstance(first, str):
            return first.strip() or None
    return None


def _category(value: object) -> str | None:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        name = value[0].get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None
    return None
