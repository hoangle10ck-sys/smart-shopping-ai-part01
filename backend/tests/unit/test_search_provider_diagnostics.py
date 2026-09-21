"""Provider diagnostics use only an in-process HTTP transport."""
from types import SimpleNamespace
import json

import httpx
import pytest

from app.services.search import tavily_provider as module
from app.services.search.base import SearchProviderError


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,kind,status', [
    ('timeout', 'timeout', None), ('429', 'rate_limit', 429),
    ('503', 'http_error', 503), ('401', 'http_error', 401),
    ('network', 'network_error', None), ('json', 'malformed_response', None),
    ('object', 'malformed_response', None), ('missing', 'malformed_response', None),
    ('item', 'malformed_response', None),
])
async def test_provider_failure_diagnostics(monkeypatch, mode, kind, status):
    original = httpx.AsyncClient
    def handle(request):
        if mode == 'timeout': raise httpx.ReadTimeout('secret-key', request=request)
        if mode == 'network': raise httpx.ConnectError('secret-key', request=request)
        if mode.isdigit(): return httpx.Response(int(mode), text='secret-key')
        if mode == 'json': return httpx.Response(200, text='secret-key')
        payload = {'object': [], 'missing': {}, 'item': {'results': [None]}}[mode]
        return httpx.Response(200, json=payload)
    monkeypatch.setattr(module, 'get_settings', lambda: SimpleNamespace(
        tavily_api_key='secret-key', search_timeout_seconds=10, search_retry_count=0))
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    with pytest.raises(SearchProviderError) as caught:
        await module.TavilyProvider().search('television', 5)
    assert caught.value.kind == kind
    assert caught.value.status_code == status
    assert 'secret-key' not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize('items', [[], [{'title': 'TV X1', 'url': 'https://shop.vn/tv-x1', 'content': 'TV'}]])
async def test_valid_empty_response_is_success(monkeypatch, items):
    original = httpx.AsyncClient
    def handle(request):
        payload = json.loads(request.content)
        assert payload['include_images'] is False
        assert payload['include_image_descriptions'] is False
        return httpx.Response(200, json={'results': items})
    monkeypatch.setattr(module, 'get_settings', lambda: SimpleNamespace(
        tavily_api_key='fake-key', search_timeout_seconds=10, search_retry_count=0))
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw: original(
        transport=httpx.MockTransport(handle), **kw))
    results = await module.TavilyProvider().search('television', 5)
    assert len(results) == len(items)
    if items: assert results[0].url == items[0]['url']
