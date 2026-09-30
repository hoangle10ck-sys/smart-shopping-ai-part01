import httpx
import pytest

from app.services.extraction.product_page_validator import inspect_page
from app.services.extraction import product_image_resolver as module
from app.services.performance import PerformanceTrace, current_trace
from tests.fixtures.cellphones_image_pages import page, OPAQUE


@pytest.mark.parametrize('index', range(3))
@pytest.mark.parametrize('pattern', ['json_ld', 'og', 'gallery', 'picture'])
@pytest.mark.asyncio
async def test_cellphones_bound_opaque_asset_recovered(monkeypatch, index, pattern):
    url, html = page(index, pattern)
    async def fetch(self, value): return value, html
    async def loads(self, value): return value == OPAQUE
    monkeypatch.setattr(module.ProductImageResolver, '_fetch_html', fetch)
    monkeypatch.setattr(module.ProductImageResolver, '_image_loads', loads)
    proof = await module.ProductImageResolver().inspect(url)
    assert proof['product_page_valid'] and proof['verification_level'] == 'VERIFIED_CONTENT'
    assert proof['image_url'] == OPAQUE


@pytest.mark.parametrize('pattern', ['cross_product', 'carousel'])
def test_opaque_unrelated_gallery_cannot_borrow_page_identity(pattern):
    url, html = page(0, pattern)
    proof = inspect_page(url, html)
    assert proof['product_page_valid'] and not proof['image_candidates']


@pytest.mark.parametrize('pattern', ['gallery', 'picture'])
def test_bound_gallery_still_rejects_explicit_wrong_model(pattern):
    url, html = page(0, pattern)
    html = html.replace(OPAQUE, 'https://cdn2.cellphones.com.vn/samsung-galaxy-s25-ultra.jpg')
    assert not inspect_page(url, html)['image_candidates']


@pytest.mark.asyncio
@pytest.mark.parametrize('mime,signature,status', [
    ('image/webp', b'RIFF' + b'\x00' * 4 + b'WEBP', 206),
    ('IMAGE/WEBP; charset=binary', b'RIFF' + b'\x00' * 4 + b'WEBP', 200),
    ('image/avif', b'\x00\x00\x00\x20ftypmif1\x00\x00\x00\x00avif', 200),
    ('image/jpeg', b'\xff\xd8\xff', 200),
])
async def test_range_get_avoids_head_and_closes_before_large_body(monkeypatch, mime, signature, status):
    original = httpx.AsyncClient
    events, methods, clients = [], [], []
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            events.append('prefix')
            yield signature + b'x' * (4096 - len(signature))
            events.append('large_tail')
            yield b'x' * 6_000_000
        async def aclose(self): events.append('closed')
    def handler(request):
        methods.append(request.method)
        if request.method == 'HEAD': return httpx.Response(403)
        assert request.headers['range'] == 'bytes=0-4095'
        return httpx.Response(status, headers={'content-type': mime, 'content-range': 'bytes 0-4095/6004096'}, stream=Stream())
    def factory(**kwargs):
        client = original(transport=httpx.MockTransport(handler), **kwargs); clients.append(client); return client
    async def public(url): return True
    monkeypatch.setattr(module, '_safe_public_url', public)
    monkeypatch.setattr(module.httpx, 'AsyncClient', factory)
    assert await module.ProductImageResolver()._image_loads(OPAQUE)
    assert methods == ['GET'] and events == ['prefix', 'closed']
    assert all(client.is_closed for client in clients)


@pytest.mark.asyncio
@pytest.mark.parametrize('target,accepted', [
    ('https://cdn.example/ab93e80f.webp?width=1200', True),
    ('https://cdn.example/samsung-galaxy-s25-ultra.jpg', False),
    ('https://cellphones.com.vn/dien-thoai-samsung-galaxy-s25-ultra.html', False),
    ('https://cdn.example/banner.jpg', False),
])
async def test_redirects_preserve_asset_identity(monkeypatch, target, accepted):
    original = httpx.AsyncClient; calls = []
    def handler(request):
        calls.append(str(request.url))
        if len(calls) == 1: return httpx.Response(302, headers={'location': target})
        return httpx.Response(200, headers={'content-type': 'image/webp'}, content=b'RIFF0000WEBP' + b'x' * 60)
    async def public(url): return True
    monkeypatch.setattr(module, '_safe_public_url', public)
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    assert await module.ProductImageResolver()._image_loads(OPAQUE) is accepted
    if not accepted: assert len(calls) == 1


def test_image_rejection_diagnostics_are_separate_from_product_validation():
    url, html = page(0)
    proof = inspect_page(url, html.replace(OPAQUE, 'https://cdn.example/logo.png'))
    assert proof['product_page_valid'] and proof['image_url'] is None
    assert proof['image_diagnostics']['accepted_count'] == 0
    assert proof['image_diagnostics']['rejections'][0]['reason'] == 'unsafe_or_decorative_url'


@pytest.mark.asyncio
async def test_probe_records_http_failure_without_exception_body(monkeypatch):
    original = httpx.AsyncClient
    async def public(url): return True
    monkeypatch.setattr(module, '_safe_public_url', public)
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(
        lambda request: httpx.Response(403, text='secret-bearing upstream error must not be logged')), **kw))
    trace = PerformanceTrace(); token = current_trace.set(trace)
    try:
        assert not await module.ProductImageResolver()._image_loads(OPAQUE)
    finally: current_trace.reset(token)
    record = trace.diagnostics['image_probes'][0]
    assert record['reason'] == 'http_status' and record['attempts'][0]['status'] == 403
    assert 'secret-bearing' not in str(trace.snapshot())
