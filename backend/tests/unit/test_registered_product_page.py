import json
from datetime import datetime, timezone

import httpx
import pytest

from app.schemas.collector import FetchStatus, SourceRegistration
from app.services.collectors.html_extractor import (
    extract_product,
    extract_visible_text,
)
from app.services.collectors.product_page import RegisteredProductPageCollector


def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def source(**overrides):
    values = {
        "source_id": "sample-shop",
        "domain": "shop.example",
        "kind": "product_page",
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


def product_html(*, price="1890000", currency="VND", sku="ABC-123"):
    product = {
        "@context": "https://schema.org",
        "@graph": [{
            "@type": ["Product"],
            "name": "Example laptop",
            "sku": sku,
            "brand": {"name": "Example"},
            "offers": {
                "@type": "Offer",
                "price": price,
                "priceCurrency": currency,
                "availability": "https://schema.org/InStock",
            },
        }],
    }
    return (
        "<html><script type='application/ld+json'>"
        + json.dumps(product)
        + "</script></html>"
    )


def test_json_ld_extracts_product_sku_and_currency_qualified_minor_units():
    observation = extract_product(
        product_html(), url="https://shop.example/p/laptop",
        platform="sample-shop", default_currency="VND", currency_minor_unit=0,
    )

    assert observation is not None
    assert observation.name == "Example laptop"
    offer = observation.offers[0]
    assert offer.identity.external_sku_id == "ABC-123"
    assert offer.sale_price == 1_890_000
    assert offer.sale_price_minor_units == 1_890_000
    assert offer.currency == "VND"
    assert {evidence.field for evidence in offer.evidence} == {"sale_price", "sku"}
    assert {evidence.json_path for evidence in offer.evidence} == {
        "offers.price", "sku"
    }


def test_json_ld_preserves_nonzero_currency_minor_units_without_vnd_major_price():
    observation = extract_product(
        product_html(price="12.34", currency="USD", sku="USD-1"),
        url="https://shop.example/p/item",
        platform="sample-shop",
        currency_minor_unit=2,
    )

    assert observation is not None
    offer = observation.offers[0]
    assert offer.sale_price is None
    assert offer.sale_price_minor_units == 1234
    assert offer.currency == "USD"
    assert offer.currency_minor_unit == 2


def test_aggregate_offer_remains_a_range_not_an_exact_sku_price():
    aggregate = {
        "@type": "Product",
        "name": "Example laptop",
        "offers": {
            "@type": "AggregateOffer",
            "lowPrice": "1000000",
            "highPrice": "1500000",
            "priceCurrency": "VND",
        },
    }
    observation = extract_product(
        "<script type='application/ld+json'>"
        + json.dumps(aggregate)
        + "</script>",
        url="https://shop.example/p/laptop",
        platform="sample-shop",
        default_currency="VND",
    )

    assert observation is not None
    offer = observation.offers[0]
    assert offer.price_range is not None
    assert offer.price_range.minimum == 1_000_000
    assert offer.price_range.maximum == 1_500_000
    assert offer.sale_price is None
    assert offer.sale_price_minor_units is None


def test_visible_text_excludes_scripts_styles_and_obeys_character_cap():
    html = (
        "<style>do not include</style><script>ignore</script>"
        "<main>RAM 16GB <b>SSD 1TB</b></main>"
    )

    assert extract_visible_text(html) == "RAM 16GB SSD 1TB"
    assert extract_visible_text(html, max_chars=6) == "RAM 16"


def test_item_list_products_are_not_mistaken_for_the_page_product():
    item_list = {
        "@type": "ItemList",
        "itemListElement": [{
            "@type": "ListItem",
            "item": {"@type": "Product", "name": "Listed item"},
        }],
    }
    html = (
        "<script type='application/ld+json'>"
        + json.dumps(item_list)
        + "</script>"
    )

    assert extract_product(
        html, url="https://shop.example/category/laptops", platform="sample-shop"
    ) is None


@pytest.mark.asyncio
async def test_registered_page_fetch_requires_robots_and_verified_product_evidence():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=product_html())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RegisteredProductPageCollector(
            client=client, resolver=public_dns
        ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.SUCCESS
    assert result.observation is not None
    assert result.observation.name == "Example laptop"
    assert result.observation.offers[0].identity.external_sku_id == "ABC-123"
    assert result.content_text == ""


@pytest.mark.asyncio
async def test_registered_page_without_exact_price_is_partial_not_success():
    body = (
        "<main>Example laptop, RAM 16GB</main>"
        "<script type='application/ld+json'>"
        + json.dumps({"@type": "Product", "name": "Example laptop"})
        + "</script>"
    )

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RegisteredProductPageCollector(
            client=client, resolver=public_dns
        ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.PARTIAL_DATA
    assert result.content_text == "Example laptop, RAM 16GB"
    assert result.observation.offers == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 429])
async def test_registered_page_fetch_does_not_bypass_access_restriction(status_code):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RegisteredProductPageCollector(
            client=client, resolver=public_dns
        ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.ACCESS_RESTRICTED
    assert result.http_status == status_code


@pytest.mark.asyncio
async def test_registered_page_fetch_rejects_external_redirect():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(302, headers={"location": "https://attacker.test/product"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RegisteredProductPageCollector(
            client=client, resolver=public_dns
        ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.INVALID_URL


@pytest.mark.asyncio
async def test_registered_page_fetch_enforces_byte_limit():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RegisteredProductPageCollector(
            client=client, max_bytes=100, resolver=public_dns
        ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.FETCH_ERROR
    assert "byte limit" in result.failure.message


@pytest.mark.asyncio
async def test_registered_page_omits_offer_urls_outside_the_approved_host():
    product = {
        "@type": "Product",
        "name": "Example laptop",
        "sku": "LAPTOP-1",
        "offers": {
            "@type": "Offer",
            "price": "1890000",
            "priceCurrency": "VND",
            "url": "https://attacker.test/product",
        },
    }
    body = (
        "<script type='application/ld+json'>"
        + json.dumps(product)
        + "</script>"
    )

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RegisteredProductPageCollector(
            client=client, resolver=public_dns
        ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.PARTIAL_DATA
    assert result.observation.offers == []
    assert any("outside the approved source host" in warning for warning in result.warnings)
