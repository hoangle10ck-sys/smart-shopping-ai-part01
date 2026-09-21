import pytest
from app.services.extraction.product_page_validator import inspect_page, same_identity
from tests.fixtures.sales_pages import sales_page


@pytest.mark.parametrize('path,kind', [('/', 'HOMEPAGE'), ('/category/phones', 'CATEGORY'),
    ('/search?q=phone', 'SEARCH_PAGE'), ('/blog/phone', 'ARTICLE'), ('/news/phone', 'NEWS'),
    ('/review/phone', 'REVIEW'), ('/products/phone-15', 'UNKNOWN')])
def test_source_classification_does_not_trust_url_alone(path, kind):
    from app.services.extraction.product_page_validator import classify_source
    assert classify_source('https://shop.vn' + path) == kind
    proof = inspect_page('https://shop.vn/products/phone-15', sales_page())
    assert proof['result_type'] == 'DIRECT_PRODUCT'


@pytest.mark.parametrize('kind', ['Article', 'NewsArticle', 'Review', 'CollectionPage', 'SearchResultsPage'])
def test_editorial_or_collection_metadata_cannot_be_sales_page(kind):
    html = sales_page() + '<script type="application/ld+json">{"@type":"' + kind + '"}</script>'
    assert not inspect_page('https://shop.vn/products/phone-15', html)['product_page_valid']


@pytest.mark.asyncio
async def test_image_timeout_does_not_discard_verified_offer(monkeypatch):
    from app.services.extraction.product_image_resolver import ProductImageResolver
    async def html(self, url): return url, sales_page(image='/photo.jpg')
    async def timeout(self, url): raise TimeoutError()
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', html)
    monkeypatch.setattr(ProductImageResolver, '_image_loads', timeout)
    proof = await ProductImageResolver().inspect('https://shop.vn/products/phone-15')
    assert proof['product_page_valid'] and proof['price'] == 9000000
    assert proof['image_url'] is None and proof['image_source'] is None


@pytest.mark.parametrize('path', ['/', '/xe-may/', '/category/phones', '/collections/phones',
                                  '/search?q=honda', '/blog/review-honda', '/tin-tuc/phone-15', '/review/phone'])
def test_nonsales_url_rejected_even_with_product_json(path):
    assert not inspect_page('https://shop.vn' + path, sales_page())['product_page_valid']


@pytest.mark.parametrize('path', ['/products/phone-model-15-128gb', '/san-pham/phone-model-15-128gb',
                                  '/dien-thoai/phone-model-15-128gb', '/listing-12345.html'])
def test_direct_page_needs_content_and_identity(path):
    url = 'https://shop.vn' + path
    assert not inspect_page(url, '<h1>Category</h1>')['product_page_valid']
    proof = inspect_page(url, sales_page(image='/images/phone-model-15-128gb.jpg'))
    assert proof['product_page_valid']
    assert proof['price'] == 9000000 and proof['merchant'] == 'Test Merchant'
    assert proof['image_candidates'] == [('https://shop.vn/images/phone-model-15-128gb.jpg', 'json_ld_product')]


@pytest.mark.parametrize('image', ['logo.png', 'favicon.ico', 'banner.jpg', 'category.jpg', 'placehoder.png', 'javascript:alert(1)', 'data:image/png;base64,x', 'phone-model-14-128gb.jpg', 'phone-model-15-pro-128gb.jpg'])
def test_bad_images_are_not_product_images(image):
    result = inspect_page('https://shop.vn/products/phone-15', sales_page(image=image))
    assert result['image_candidates'] == []
    assert result['image_url'] is None


def test_metadata_and_html_image_fallbacks():
    html = sales_page() + '<meta property="og:image" content="/photo.jpg">'
    proof = inspect_page('https://shop.vn/products/phone-15', html)
    assert proof['image_candidates'][0] == ('https://shop.vn/photo.jpg', 'og:image')
    html = sales_page() + '<img alt="Phone Model 15 128GB" src="/phone.jpg">'
    assert inspect_page('https://shop.vn/products/phone-15', html)['image_candidates'][0][1] == 'html_product_image'
    assert inspect_page('https://shop.vn/products/phone-15', sales_page())['image_url'] is None


def test_html_marked_price_and_buy_action_can_verify_direct_page():
    html = '<h1>Phone Model 15 128GB</h1><span itemprop="price">9.000.000đ</span><button>Mua ngay</button>'
    assert inspect_page('https://shop.vn/products/phone-15', html)['price'] == 9000000
    assert not inspect_page('https://shop.vn/products/phone-15', html.replace('Mua ngay', 'Review'))['product_page_valid']


def test_manufacturer_without_purchase_action_is_not_a_sales_offer():
    html = sales_page(name='Honda Wave Alpha 110', brand='Honda').replace('<button>Mua ngay</button>', '')
    assert not inspect_page('https://www.honda.com.vn/xe-may/san-pham/wave-alpha-110', html)['product_page_valid']


@pytest.mark.parametrize('price', [9000000, 9000000.0, '9000000.00', '9.000.000'])
def test_structured_decimal_price_is_not_display_grouping(price):
    assert inspect_page('https://shop.vn/products/phone-15', sales_page(price=price))['price'] == 9000000


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,expected', [('jpeg', True), ('html', False), ('404', False), ('private_redirect', False), ('logo_redirect', False)])
async def test_image_http_validation_without_network(monkeypatch, mode, expected):
    import httpx
    from app.services.extraction import product_image_resolver as module
    original = httpx.AsyncClient
    calls = []
    def handle(request):
        calls.append(str(request.url))
        if mode == 'private_redirect': return httpx.Response(302, headers={'location': 'http://127.0.0.1/private.jpg'})
        if mode == 'logo_redirect': return httpx.Response(302, headers={'location': 'https://shop.vn/logo.jpg'})
        if mode == '404': return httpx.Response(404)
        if mode == 'html': return httpx.Response(200, headers={'content-type': 'text/html'}, content=b'<html>blocked</html>')
        return httpx.Response(200, headers={'content-type': 'image/jpeg'}, content=b'\xff\xd8\xff' + b'x' * 100 + b'\xff\xd9')
    async def public(url): return not url.startswith('http://127.')
    monkeypatch.setattr(module, '_safe_public_url', public)
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    assert await module.ProductImageResolver()._image_loads('https://shop.vn/photo.jpg') is expected
    assert len(calls) == 1


@pytest.mark.parametrize('a,b', [('iPhone 15 128GB', 'iPhone 15 Pro 128GB'), ('iPhone 15 128GB', 'iPhone 15 256GB'),
                               ('Honda Wave Alpha 110', 'Honda Wave RSX'), ('Honda Super Cub C125', 'Honda Wave Alpha 110')])
def test_wrong_model_variant_or_capacity_never_matches(a, b):
    assert not same_identity(a, b)
    assert not inspect_page('https://shop.vn/products/model', sales_page(name=b), a)['product_page_valid']


@pytest.mark.parametrize('name,image', [('Honda Wave Alpha 110', 'honda-super-cub-c125.jpg'),
                                      ('Samsung UA43AU7000', 'samsung-ua55au7000.jpg')])
def test_image_of_another_model_with_same_brand_is_rejected(name, image):
    proof = inspect_page('https://shop.vn/products/model', sales_page(name=name, image=image))
    assert proof['product_page_valid']
    assert proof['image_candidates'] == []


def test_carousel_wrong_product_and_range_price_rejected():
    html = sales_page() .replace('<h1>Phone Model 15 128GB</h1>', '<h1>Phone Model 16 128GB</h1>')
    assert not inspect_page('https://shop.vn/products/model', html)['product_page_valid']
    html = sales_page(offers={'@type': 'AggregateOffer', 'lowPrice': 1, 'highPrice': 99, 'priceCurrency': 'VND'})
    assert not inspect_page('https://shop.vn/products/model', html)['product_page_valid']


@pytest.mark.asyncio
async def test_resolver_rejects_broken_image_and_preserves_page(monkeypatch):
    from app.services.extraction.product_image_resolver import ProductImageResolver
    async def html(self, url): return url, sales_page(image='/photo.jpg')
    async def broken(self, url): return False
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', html)
    monkeypatch.setattr(ProductImageResolver, '_image_loads', broken)
    proof = await ProductImageResolver().inspect('https://shop.vn/products/phone-15')
    assert proof['product_page_valid'] and proof['image_url'] is None


@pytest.mark.asyncio
async def test_resolver_uses_verified_product_image(monkeypatch):
    from app.services.extraction.product_image_resolver import ProductImageResolver
    async def html(self, url): return url, sales_page(image='/photo.jpg')
    async def loads(self, url): return True
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', html)
    monkeypatch.setattr(ProductImageResolver, '_image_loads', loads)
    proof = await ProductImageResolver().inspect('https://shop.vn/products/phone-15')
    assert proof['image_url'] == 'https://shop.vn/photo.jpg'
    assert proof['image_source'] == 'json_ld_product'
