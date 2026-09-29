"""Offline image patterns; synthetic HTML is not historical retailer HTML."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.extraction.product_page_validator import inspect_page
from tests.fixtures.sales_pages import sales_page

URL = 'https://shop.example/products/phone-model-15-128gb'
NAME = 'Phone Model 15 128GB'


@pytest.mark.parametrize('image', [
    '/images/phone-model-15-128gb.jpg',
    ['/logo.png', '/images/phone-model-15-128gb.jpg'],
    {'@type': 'ImageObject', 'url': '/images/phone-model-15-128gb.jpg'},
    {'@type': 'ImageObject', 'contentUrl': '/images/phone-model-15-128gb.jpg'},
    {'@type': 'ImageObject', 'url': '/logo.png', 'contentUrl': '/images/phone-model-15-128gb.jpg'},
])
def test_json_ld_shapes(image):
    proof = inspect_page(URL, sales_page(image=image))
    assert proof['image_candidates'][0] == ('https://shop.example/images/phone-model-15-128gb.jpg', 'json_ld_product')


@pytest.mark.parametrize('attribute,value', [
    ('src', '/images/phone-model-15-128gb.jpg'),
    ('data-src', '/images/phone-model-15-128gb.jpg'),
    ('data-original', '/images/phone-model-15-128gb.jpg'),
    ('data-lazy-src', '/images/phone-model-15-128gb.jpg'),
    ('srcset', '/images/phone-model-15-128gb.jpg 600w, /images/phone-model-15-128gb-1200x1200.jpg 1200w'),
    ('data-srcset', '/images/phone-model-15-128gb.jpg 1x, /images/phone-model-15-128gb-1200x1200.jpg 2x'),
])
def test_bound_gallery_lazy_and_srcset(attribute, value):
    html = sales_page() + f'<img alt="{NAME}" src="/placeholder.png" {attribute}="{value}">'
    proof = inspect_page(URL, html)
    assert proof['image_candidates']
    assert all('placeholder' not in url for url, _ in proof['image_candidates'])
    assert all(origin == 'html_product_image' for _, origin in proof['image_candidates'])


@pytest.mark.parametrize('raw,expected', [
    ('../images/photo.jpg', 'https://shop.example/images/photo.jpg'),
    ('//cdn.example/photo.jpg', 'https://cdn.example/photo.jpg'),
    (r'https:\/\/cdn.example\/photo.jpg?x=1&amp;y=2', 'https://cdn.example/photo.jpg?x=1&y=2'),
])
def test_normalization(raw, expected):
    proof = inspect_page(URL, sales_page(image=raw))
    assert proof['image_candidates'] == [(expected, 'json_ld_product')]


@pytest.mark.parametrize('key', ['og:image', 'og:image:secure_url', 'twitter:image', 'twitter:image:src'])
def test_verified_meta_fallback(key):
    proof = inspect_page(URL, sales_page() + f'<meta property="{key}" content="/photo.jpg">')
    assert proof['product_page_valid'] and proof['image_candidates'] == [('https://shop.example/photo.jpg', key)]


def test_priority_and_url_deduplication():
    html = sales_page(image='/json.jpg', associatedMedia={'@type': 'ImageObject', 'contentUrl': '/structured.jpg'})
    html += '<meta property="og:image" content="/json.jpg"><meta name="twitter:image" content="/meta.jpg">'
    html += f'<img alt="{NAME}" src="/gallery.jpg">'
    assert inspect_page(URL, html)['image_candidates'] == [
        ('https://shop.example/json.jpg', 'json_ld_product'),
        ('https://shop.example/structured.jpg', 'structured_product_media'),
        ('https://shop.example/meta.jpg', 'twitter:image'),
        ('https://shop.example/gallery.jpg', 'html_product_image'),
    ]


@pytest.mark.parametrize('image', ['data:image/png;base64,x', 'javascript:alert(1)', '/transparent.gif',
    '/pixel.gif', '/1x1.png', '/loading.jpg', '/logo.jpg', '/favicon.ico', '/sale-banner.jpg', '/placeholder.jpg',
    '/phone-model-16-128gb.jpg', '/phone-model-15-pro-128gb.jpg', '/phone-model-15-256gb.jpg'])
def test_invalid_or_wrong_model(image):
    proof = inspect_page(URL, sales_page(image=image))
    assert proof['product_page_valid'] and not proof['image_candidates']


@pytest.mark.parametrize('kind', ['Article', 'NewsArticle', 'Review', 'CollectionPage', 'ItemList'])
def test_nonsales_never_promotes_images(kind):
    html = sales_page(image='/photo.jpg') + '<meta property="og:image" content="/photo.jpg">'
    html += '<script type="application/ld+json">' + json.dumps({'@type': kind}) + '</script>'
    proof = inspect_page(URL, html)
    assert not proof['product_page_valid'] and not proof.get('image_candidates') and proof['image_url'] is None


@pytest.mark.parametrize('source', ['json_name', 'json_caption', 'og_alt', 'twitter_alt', 'html_alt'])
def test_explicit_metadata_conflict_rejects_opaque_or_correct_filename(source):
    other = 'Phone Model 16 128GB'
    if source.startswith('json'):
        image = {'url': '/phone-model-15-128gb.jpg', source.split('_')[1]: other}
        html = sales_page(image=image)
    elif source == 'html_alt':
        html = sales_page() + f'<img alt="{other}" src="/phone-model-15-128gb.jpg">'
    else:
        key = 'og' if source == 'og_alt' else 'twitter'
        html = sales_page() + f'<meta property="{key}:image" content="/opaque.jpg"><meta property="{key}:image:alt" content="{other}">'
    proof = inspect_page(URL, html)
    assert not proof['image_candidates']


def test_structured_other_product_is_not_promoted_and_unbound_gallery_stays_unknown():
    html = sales_page() + '<script type="application/ld+json">' + json.dumps({
        '@type': 'Product', 'name': 'Phone Model 16 128GB', 'image': '/other.jpg'}) + '</script>'
    html += '<div class="product-gallery"><img src="/opaque.jpg"></div>'
    assert not inspect_page(URL, html)['image_candidates']


def test_dimensions_not_model_but_arbitrary_digits_remain_conflicts():
    good = inspect_page(URL, sales_page(image='/phone-model-15-128gb-600x600.jpg'))
    bad = inspect_page(URL, sales_page(image='/phone-model-15-128gb-2026.jpg'))
    assert good['image_candidates'] and not bad['image_candidates']


@pytest.mark.asyncio
async def test_broken_primary_tries_lazy_fallback_without_changing_offer(monkeypatch):
    from app.services.extraction.product_image_resolver import ProductImageResolver
    html = sales_page(image='/broken.jpg') + f'<img alt="{NAME}" data-original="/phone-model-15-128gb.jpg">'
    before = inspect_page(URL, html)
    async def fetch(self, url): return url, html
    async def loads(self, url): return not url.endswith('/broken.jpg')
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', fetch)
    monkeypatch.setattr(ProductImageResolver, '_image_loads', loads)
    proof = await ProductImageResolver().inspect(URL)
    assert proof['image_url'] == 'https://shop.example/phone-model-15-128gb.jpg'
    assert proof['image_source'] == 'html_product_image'
    for key in ('name', 'price', 'merchant', 'availability', 'product_page_valid', 'verification_level'):
        assert proof[key] == before[key]


def test_archived_nulls_are_not_rewritten_by_synthetic_recovery():
    path = Path(__file__).parents[1] / 'fixtures/image_snapshot_de9c2e2a.json'
    archived = json.loads(path.read_text(encoding='utf8'))
    original = deepcopy(archived)
    assert len(archived['recommendations']) == 3
    for rec in archived['recommendations']:
        assert rec['verification_level'] == 'VERIFIED_CONTENT' and rec['image_url'] is None
        # Explicitly synthetic same-product lazy pattern; never a claimed Live image.
        html = sales_page(name=rec['name'], price=rec['price']) + f'<img alt="{rec["name"]}" data-original="/synthetic-fixture-photo.jpg">'
        assert inspect_page(rec['product_url'], html)['image_candidates']
    assert archived == original


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['pixel_gif', 'pixel_png', 'other_model_redirect', 'placeholder_redirect'])
async def test_probe_rejects_pixels_and_redirected_wrong_images(monkeypatch, mode):
    import httpx
    from app.services.extraction import product_image_resolver as module
    original = httpx.AsyncClient
    calls = []
    def handle(request):
        calls.append(str(request.url))
        if len(calls) == 1 and mode.endswith('redirect'):
            target = '/phone-model-16-128gb.jpg' if mode == 'other_model_redirect' else '/transparent.gif'
            return httpx.Response(302, headers={'location': target})
        if mode == 'pixel_gif':
            return httpx.Response(200, headers={'content-type': 'image/gif'}, content=b'GIF89a\x01\x00\x01\x00' + b'x' * 40)
        if mode == 'pixel_png':
            raw = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + b'\x00\x00\x00\x01' * 2 + b'x' * 40
            return httpx.Response(200, headers={'content-type': 'image/png'}, content=raw)
        return httpx.Response(200, headers={'content-type': 'image/jpeg'}, content=b'\xff\xd8\xff' + b'x' * 100)
    async def public(url): return True
    monkeypatch.setattr(module, '_safe_public_url', public)
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    assert not await module.ProductImageResolver()._image_loads('https://shop.example/phone-model-15-128gb.jpg')
    if mode.endswith('redirect'): assert len(calls) == 1


def test_itemprop_cannot_override_conflicting_title():
    html = sales_page() + f'<img itemprop="image" alt="{NAME}" title="Phone Model 16 128GB" src="/opaque.jpg">'
    assert not inspect_page(URL, html)['image_candidates']
