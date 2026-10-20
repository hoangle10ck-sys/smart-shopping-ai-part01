import httpx
import pytest

from app.schemas.collector import FetchStatus
from app.services.collectors.lazada import LazadaCollector
from app.services.collectors.shopee import ShopeeCollector
from app.services.collectors.url_safety import UnsafeURL, validate_marketplace_url


PRODUCT = b'''<html><head><meta property="og:title" content="Demo Phone">
<script type="application/ld+json">{"@type":"Product","name":"Demo Phone","brand":{"name":"Demo"},
"aggregateRating":{"ratingValue":"4.8","reviewCount":"12"},"offers":{"@type":"Offer","price":"1990000",
"priceCurrency":"VND","availability":"InStock","sku":"sku-256","seller":{"name":"Official"}}}</script>
</head></html>'''


@pytest.mark.asyncio
async def test_shopee_jsonld_fixture_is_extracted_without_network():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type":"text/html"}, content=PRODUCT))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await ShopeeCollector(client=client, resolve_dns=False).fetch("https://shopee.vn/demo-i.1.2")
    assert result.status == FetchStatus.SUCCESS
    assert result.observation.offers[0].sale_price == 1_990_000
    assert result.observation.offers[0].identity.external_sku_id == "sku-256"
    assert result.observation.offers[0].identity.external_product_id == "2"
    assert result.observation.offers[0].identity.external_shop_id == "1"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429])
async def test_access_controls_are_not_bypassed(status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, headers={"content-type":"text/html"}))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await LazadaCollector(client=client, resolve_dns=False).fetch("https://www.lazada.vn/products/demo-i1.html")
    assert result.status == FetchStatus.ACCESS_RESTRICTED


@pytest.mark.asyncio
async def test_captcha_and_large_html_are_structured_failures():
    captcha = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type":"text/html"}, text="CAPTCHA"))
    async with httpx.AsyncClient(transport=captcha) as client:
        result = await ShopeeCollector(client=client, resolve_dns=False).fetch("https://shopee.vn/demo-i.1.2")
    assert result.status == FetchStatus.ACCESS_RESTRICTED
    huge = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type":"text/html"}, content=b"x" * 2_000_001))
    async with httpx.AsyncClient(transport=huge) as client:
        result = await ShopeeCollector(client=client, resolve_dns=False).fetch("https://shopee.vn/demo-i.1.2")
    assert result.status == FetchStatus.PROVIDER_FAILED


def test_url_allowlist_blocks_fake_hosts_and_private_dns():
    with pytest.raises(UnsafeURL):
        validate_marketplace_url("https://shopee.vn.attacker.test/item", resolve_dns=False)
    with pytest.raises(UnsafeURL):
        validate_marketplace_url("file:///etc/passwd", resolve_dns=False)
    resolver = lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))]
    with pytest.raises(UnsafeURL):
        validate_marketplace_url("https://shopee.vn/item", resolver=resolver)


@pytest.mark.asyncio
async def test_redirect_outside_allowlist_is_rejected():
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={"location":"http://127.0.0.1/secret"}))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await ShopeeCollector(client=client, resolve_dns=False).fetch("https://shopee.vn/demo-i.1.2")
    assert result.status == FetchStatus.INVALID_URL


@pytest.mark.asyncio
async def test_timeout_is_provider_failure_and_never_empty_catalog():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        result = await LazadaCollector(client=client, resolve_dns=False).fetch("https://www.lazada.vn/products/demo-i1.html")
    assert result.status == FetchStatus.PROVIDER_FAILED
    assert result.failure.retryable is True


@pytest.mark.asyncio
async def test_product_without_price_is_partial_and_range_is_not_exact_price():
    no_price = b'<meta property="og:title" content="JS Product">'
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type":"text/html"}, content=no_price))) as client:
        result = await ShopeeCollector(client=client, resolve_dns=False).fetch("https://shopee.vn/js-i.1.2")
    assert result.status == FetchStatus.PARTIAL_DATA
    ranged = b'<script type="application/ld+json">{"@type":"Product","name":"Many SKUs","offers":{"lowPrice":"100","highPrice":"200"}}</script>'
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type":"text/html"}, content=ranged))) as client:
        result = await LazadaCollector(client=client, resolve_dns=False).fetch("https://www.lazada.vn/products/many-i1.html")
    offer = result.observation.offers[0]
    assert offer.price_range.minimum == 100 and offer.price_range.maximum == 200
    assert offer.sale_price is None and offer.listed_price is None


@pytest.mark.asyncio
async def test_multiple_skus_remain_separate_offers():
    body = b'<script type="application/ld+json">{"@type":"Product","name":"Phone","offers":[{"price":"100","sku":"128"},{"price":"200","sku":"256"}]}</script>'
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type":"text/html"}, content=body))) as client:
        result = await ShopeeCollector(client=client, resolve_dns=False).fetch("https://shopee.vn/phone-i.1.2")
    assert [(item.identity.external_sku_id, item.sale_price) for item in result.observation.offers] == [("128", 100), ("256", 200)]
