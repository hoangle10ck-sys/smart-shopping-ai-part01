import json
from datetime import datetime, timezone

import httpx
import pytest

from app.schemas.collector import (
    FetchStatus,
    FieldEvidence,
    OfferObservation,
    ProductObservation,
    SourceFetchResult,
    SourceRegistration,
    VariantIdentity,
)
from app.services.collectors.service import CollectorService
from app.services.collectors.source_registry import SourceRegistry
from app.services.collectors.browser_renderer import RenderedPage
from app.services.search.search_service import SearchService


def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def approved_source(kind, **overrides):
    values = {
        "source_id": "sample-store",
        "domain": "shop.example",
        "kind": kind,
        "permission_status": "approved",
        "permission_basis": "Written merchant approval.",
        "terms_url": "https://shop.example/terms",
        "terms_checked_at": datetime(2026, 10, 15, tzinfo=timezone.utc),
        "enabled": True,
        "allowed_paths": ["/"],
        "default_currency": "VND",
        "currency_minor_unit": 0,
    }
    values.update(overrides)
    return SourceRegistration(**values)


@pytest.mark.asyncio
async def test_collector_service_routes_registered_product_page(monkeypatch):
    from app.services.collectors import service as service_module

    original_client = httpx.AsyncClient

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        product = {
            "@type": "Product",
            "name": "Example laptop",
            "sku": "LAPTOP-1",
            "offers": {
                "@type": "Offer",
                "price": "1890000",
                "priceCurrency": "VND",
            },
        }
        html = (
            "<script type='application/ld+json'>"
            + json.dumps(product)
            + "</script>"
        )
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text=html
        )

    client_factory = lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler)
    )
    service = CollectorService(
        enabled=True,
        registry=SourceRegistry([approved_source("product_page")]),
        resolver=public_dns,
        http_client_factory=client_factory,
    )
    monkeypatch.setattr(service.settings, "collector_min_interval_seconds", 0)

    result = await service.fetch("https://shop.example/product/laptop")

    assert result.status == FetchStatus.SUCCESS
    assert result.platform == "sample-store"
    assert result.observation.offers[0].identity.external_sku_id == "LAPTOP-1"


@pytest.mark.asyncio
async def test_collector_service_uses_browser_only_for_js_shell(monkeypatch):
    from app.services.collectors import service as service_module

    original_client = httpx.AsyncClient

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><div id='__next'></div><script>boot()</script></html>",
        )

    client_factory = lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler)
    )

    product = {
        "@type": "Product",
        "name": "Rendered headset",
        "sku": "HEADSET-1",
        "offers": {"@type": "Offer", "price": "990000", "priceCurrency": "VND"},
    }

    class FakeRenderer:
        calls = []

        async def render(self, url):
            self.calls.append(url)
            return RenderedPage(
                "<script type='application/ld+json'>" + json.dumps(product) + "</script>",
                url,
            )

    renderer = FakeRenderer()
    service = CollectorService(
        enabled=True,
        registry=SourceRegistry([approved_source("product_page")]),
        resolver=public_dns,
        browser_renderer=renderer,
        http_client_factory=client_factory,
    )
    monkeypatch.setattr(service.settings, "collector_min_interval_seconds", 0)
    monkeypatch.setattr(service.settings, "collector_browser_enabled", True)

    result = await service.fetch("https://shop.example/product/headset")

    assert result.status == FetchStatus.SUCCESS
    assert result.observation.name == "Rendered headset"
    assert renderer.calls == ["https://shop.example/product/headset"]


@pytest.mark.asyncio
async def test_collector_service_searches_approved_store_api(monkeypatch):
    from app.services.collectors import service as service_module

    original_client = httpx.AsyncClient
    payload = [{
        "id": 7,
        "name": "Example laptop",
        "sku": "LAPTOP-7",
        "permalink": "https://shop.example/product/laptop/",
        "prices": {
            "price": "1890000",
            "regular_price": "2000000",
            "currency_code": "VND",
            "currency_minor_unit": 0,
        },
        "is_in_stock": True,
        "images": [],
    }]

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, json=payload)

    client_factory = lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler)
    )
    service = CollectorService(
        enabled=True,
        registry=SourceRegistry([approved_source("woocommerce_store_api")]),
        resolver=public_dns,
        http_client_factory=client_factory,
    )
    monkeypatch.setattr(service.settings, "collector_min_interval_seconds", 0)

    results = await service.search_registered_sources("laptop")

    assert len(results) == 1
    assert results[0].status == FetchStatus.SUCCESS
    assert results[0].products[0].observation.offers[0].identity.external_sku_id == "LAPTOP-7"


def test_search_service_keeps_api_observation_distinct_from_page_validity():
    result = SourceFetchResult(
        status=FetchStatus.SUCCESS,
        source_url="https://shop.example/product/laptop/",
        source_domain="shop.example",
        platform="sample-store",
        content_type="application/json",
        observation=ProductObservation(
            name="Example laptop",
            evidence=[
                FieldEvidence(
                    field="name",
                    value="Example laptop",
                    source_url="https://shop.example/wp-json/wc/store/v1/products",
                    evidence_type="PUBLIC_API",
                    verification_status="VERIFIED",
                )
            ],
            offers=[
                OfferObservation(
                    identity=VariantIdentity(
                        platform="sample-store",
                        external_product_id="7",
                        external_sku_id="LAPTOP-7",
                    ),
                    sale_price=1_890_000,
                    sale_price_minor_units=1_890_000,
                    currency_minor_unit=0,
                    currency="VND",
                    product_url="https://shop.example/product/laptop/",
                    evidence=[
                        FieldEvidence(
                            field="price",
                            value={"minor_units": 1_890_000, "currency": "VND"},
                            source_url="https://shop.example/wp-json/wc/store/v1/products",
                            evidence_type="PUBLIC_API",
                            verification_status="VERIFIED",
                        )
                    ],
                )
            ],
        ),
    )

    source = SearchService._collector_sources(result)[0]

    assert source.page_validation["product_page_valid"] is False
    assert source.page_validation["source_observation_valid"] is True
    assert source.page_validation["price"] == 1_890_000
    assert source.domain == "shop.example"
