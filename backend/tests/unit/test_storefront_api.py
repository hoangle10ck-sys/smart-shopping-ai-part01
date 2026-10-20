from datetime import datetime, timezone

import httpx
import pytest

from app.schemas.collector import FetchStatus, SourceRegistration
from app.services.collectors.storefront_api import WooCommerceStoreAPICollector


def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def source(**overrides):
    values = {
        "source_id": "sample-store-api",
        "domain": "shop.example",
        "kind": "woocommerce_store_api",
        "permission_status": "approved",
        "permission_basis": "Written merchant approval.",
        "terms_url": "https://shop.example/terms",
        "terms_checked_at": datetime(2026, 10, 15, tzinfo=timezone.utc),
        "enabled": True,
        "allowed_paths": ["/"],
    }
    values.update(overrides)
    return SourceRegistration(**values)


def product(*, product_type="simple", sku="SKU-1"):
    return {
        "id": 21,
        "name": "Example device",
        "slug": "example-device",
        "type": product_type,
        "sku": sku,
        "permalink": "https://shop.example/product/example-device/",
        "prices": {
            "price": "1234",
            "regular_price": "1500",
            "currency_code": "USD",
            "currency_minor_unit": 2,
        },
        "is_in_stock": True,
        "images": [],
    }


@pytest.mark.asyncio
async def test_store_api_preserves_currency_minor_units_and_source_evidence():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, json=[product()])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "device", max_products=1)

    assert result.status == FetchStatus.SUCCESS
    offer = result.products[0].observation.offers[0]
    assert offer.currency == "USD"
    assert offer.currency_minor_unit == 2
    assert offer.sale_price is None
    assert offer.sale_price_minor_units == 1234
    assert offer.listed_price_minor_units == 1500
    assert offer.identity.external_sku_id == "SKU-1"
    assert {evidence.evidence_type for evidence in offer.evidence} == {"PUBLIC_API"}
    assert {evidence.json_path for evidence in offer.evidence} == {
        "prices.price", "sku"
    }
    assert result.products[0].observation.evidence[0].json_path == "name"


@pytest.mark.asyncio
async def test_store_api_bounds_paging_and_skips_repeated_product_ids():
    requested_pages = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        page_number = int(request.url.params["page"])
        requested_pages.append(page_number)
        ids = range(20) if page_number == 1 else [0, 20, 21]
        products = []
        for product_id in ids:
            item = product()
            item["id"] = product_id
            item["sku"] = f"SKU-{product_id}"
            item["permalink"] = f"https://shop.example/product/{product_id}/"
            products.append(item)
        return httpx.Response(200, json=products)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, max_pages=5, min_interval_seconds=0, resolver=public_dns
        ).search(source(max_products=30), "device", max_products=25)

    product_ids = [
        item.observation.offers[0].identity.external_product_id
        for item in result.products
    ]
    assert requested_pages == [1, 2]
    assert len(product_ids) == len(set(product_ids)) == 22
    assert result.status == FetchStatus.PARTIAL_DATA
    assert any("duplicate source product ID" in item for item in result.warnings)


@pytest.mark.asyncio
async def test_store_api_does_not_treat_variable_product_without_sku_as_exact_offer():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200, json=[product(product_type="variable", sku="PARENT-SKU")]
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "device", max_products=1)

    assert result.status == FetchStatus.PARTIAL_DATA
    offer = result.products[0].observation.offers[0]
    assert offer.identity.external_sku_id is None
    assert offer.sale_price_minor_units is None
    assert offer.listed_price_minor_units is None


@pytest.mark.asyncio
async def test_store_api_marks_missing_sku_partial_without_discarding_verified_price():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, json=[product(sku="")])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "device", max_products=1)

    assert result.status == FetchStatus.PARTIAL_DATA
    offer = result.products[0].observation.offers[0]
    assert offer.sale_price_minor_units == 1234
    assert offer.identity.external_sku_id is None


@pytest.mark.asyncio
async def test_store_api_reports_restricted_responses_without_retrying_or_fallback():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(429)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "device", max_products=1)

    assert result.status == FetchStatus.ACCESS_RESTRICTED
    assert result.failure.retryable is True
    assert calls.count("/wp-json/wc/store/v1/products") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 429])
async def test_store_api_stops_for_restricted_http_status(status_code):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            status_code,
            headers={"retry-after": "17"} if status_code == 429 else None,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(
            source(domain=f"restricted-{status_code}.example"),
            "device",
            max_products=1,
        )

    assert result.status == FetchStatus.ACCESS_RESTRICTED
    assert result.failure.http_status == status_code
    assert result.failure.retryable is (status_code == 429)
    assert result.failure.retry_after_seconds == (17 if status_code == 429 else None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        ("text/html", b"<html>not json</html>"),
        ("application/json", b"{malformed"),
    ],
)
async def test_store_api_rejects_non_json_and_malformed_payloads(content_type, body):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200, headers={"content-type": content_type}, content=body
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "device", max_products=1)

    assert result.status == FetchStatus.FETCH_ERROR
    assert result.failure is not None


@pytest.mark.asyncio
async def test_store_api_empty_result_is_successful_and_empty():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "missing", max_products=1)

    assert result.status == FetchStatus.SUCCESS
    assert result.products == []


@pytest.mark.asyncio
async def test_store_api_rejects_oversized_payload_before_json_parsing():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(
            200, headers={"content-type": "application/json"}, content=b" " * 300
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await WooCommerceStoreAPICollector(
            client=client, max_bytes=100, min_interval_seconds=0, resolver=public_dns
        ).search(source(), "device", max_products=1)

    assert result.status == FetchStatus.FETCH_ERROR
    assert result.failure.message == "Store API response exceeds byte limit."
