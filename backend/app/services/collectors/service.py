"""Route direct URLs and registered sources to permitted collectors."""

import socket
from urllib.parse import urlsplit

from app.schemas.collector import (
    CollectorFailure,
    FetchStatus,
    SourceFetchResult,
    SourceRegistration,
)
from app.services.collectors.lazada import LazadaCollector
from app.services.collectors.network_policy import build_pinned_http_client
from app.services.collectors.product_page import RegisteredProductPageCollector
from app.services.collectors.shopee import ShopeeCollector
from app.services.collectors.source_registry import SourceRegistry
from app.services.collectors.storefront_api import WooCommerceStoreAPICollector
from app.services.collectors.url_safety import UnsafeURL, validate_marketplace_url


class CollectorService:
    def __init__(
        self,
        *,
        shopee=None,
        lazada=None,
        resolve_dns: bool = True,
        enabled: bool | None = None,
        registry: SourceRegistry | None = None,
        resolver=None,
        browser_renderer=None,
        http_client_factory=None,
    ):
        from app.core.config import get_settings

        self.resolve_dns = resolve_dns
        self.resolver = resolver or socket.getaddrinfo
        settings = get_settings()
        self.settings = settings
        self.browser_renderer = browser_renderer
        self.http_client_factory = http_client_factory or build_pinned_http_client
        self.enabled = (settings.collector_live_enabled and settings.collector_policy_confirmed) if enabled is None else enabled
        self.registry = registry or SourceRegistry.from_json(
            settings.collector_source_registry_json
        )
        self.collectors = {
            "shopee": shopee or ShopeeCollector(resolve_dns=resolve_dns),
            "lazada": lazada or LazadaCollector(resolve_dns=resolve_dns),
        }

    async def fetch(self, url: str) -> SourceFetchResult:
        registered = self.registry.resolve_url(url)
        if registered is not None:
            if not self.enabled:
                return self._failure(
                    url,
                    registered,
                    FetchStatus.SOURCE_NOT_PERMITTED,
                    "Live collector is disabled until the operator confirms written permission/policy.",
                )
            if registered.kind != "product_page":
                return self._failure(
                    url,
                    registered,
                    FetchStatus.NOT_PRODUCT_PAGE,
                    "This registered source is a search API; use a product search query.",
                )
            async with self.http_client_factory(
                allowed_domains=[registered.domain],
                allow_subdomains=registered.allow_subdomains,
                resolver=self.resolver,
                timeout=self.settings.collector_http_timeout_seconds,
            ) as client:
                result = await RegisteredProductPageCollector(
                    client=client,
                    max_bytes=self.settings.collector_max_bytes,
                    min_interval_seconds=self.settings.collector_min_interval_seconds,
                    max_content_chars=min(
                        12000,
                        max(0, self.settings.llm_extraction_max_input_chars),
                    ),
                    resolver=self.resolver,
                ).fetch(url, registered)
                if not (
                    self.settings.collector_browser_enabled
                    and result.status == FetchStatus.NOT_PRODUCT_PAGE
                    and "JS_RENDERING_CANDIDATE" in result.warnings
                ):
                    return result
                from app.services.collectors.browser_product_page import BrowserProductPageCollector
                from app.services.collectors.browser_renderer import Crawl4AIRenderer

                renderer = self.browser_renderer or Crawl4AIRenderer(
                    timeout_seconds=self.settings.collector_browser_timeout_seconds,
                    allowed_domain=urlsplit(result.source_url).hostname,
                    resolver=self.resolver,
                )
                return await BrowserProductPageCollector(
                    renderer=renderer,
                    max_bytes=min(
                        self.settings.collector_max_bytes,
                        self.settings.collector_browser_max_dom_bytes,
                    ),
                    max_content_chars=min(
                        12000, max(0, self.settings.llm_extraction_max_input_chars)
                    ),
                    resolver=self.resolver,
                ).fetch(result.source_url, registered)

        try:
            validated = validate_marketplace_url(url, resolve_dns=self.resolve_dns)
        except UnsafeURL as exc:
            return SourceFetchResult(status=FetchStatus.INVALID_URL, source_url=url, platform="unknown",
                failure=CollectorFailure(code=FetchStatus.INVALID_URL, message=str(exc)))
        if not self.enabled:
            return SourceFetchResult(status=FetchStatus.ACCESS_RESTRICTED, source_url=validated.url,
                platform=validated.platform, failure=CollectorFailure(code=FetchStatus.ACCESS_RESTRICTED,
                message="Live collector is disabled until the operator confirms written permission/policy."))
        return await self.collectors[validated.platform].fetch(validated.url)

    async def search_registered_sources(self, query: str):
        """Search explicitly enabled public storefront APIs for one query."""
        if not self.enabled:
            return []
        sources = [
            source for source in self.registry.enabled()
            if source.kind == "woocommerce_store_api"
        ]
        if not sources:
            return []
        results = []
        for source in sources:
            async with self.http_client_factory(
                allowed_domains=[source.domain],
                allow_subdomains=source.allow_subdomains,
                resolver=self.resolver,
                timeout=self.settings.collector_http_timeout_seconds,
            ) as client:
                collector = WooCommerceStoreAPICollector(
                    client=client,
                    max_bytes=self.settings.collector_max_bytes,
                    max_pages=self.settings.collector_max_pages,
                    min_interval_seconds=self.settings.collector_min_interval_seconds,
                    resolver=self.resolver,
                )
                results.append(await collector.search(
                    source, query, max_products=source.max_products
                ))
        return results

    @staticmethod
    def _failure(
        url: str,
        source: SourceRegistration,
        status: FetchStatus,
        message: str,
    ) -> SourceFetchResult:
        return SourceFetchResult(
            status=status,
            source_url=url,
            source_domain=source.domain,
            platform=source.source_id,
            failure=CollectorFailure(code=status, message=message),
        )
