import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.services.search.base import SearchProviderError
from app.services.search.searxng_provider import SearXNGProvider


def _provider_for_response(monkeypatch, handler):
    settings = SimpleNamespace(
        searxng_base_url="http://searxng.test",
        search_timeout_seconds=1,
    )
    monkeypatch.setattr(
        "app.services.search.searxng_provider.get_settings",
        lambda: settings,
    )
    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        )

    monkeypatch.setattr(
        "app.services.search.searxng_provider.httpx.AsyncClient",
        client_factory,
    )
    return SearXNGProvider()


@pytest.mark.parametrize(
    "payload",
    [[], {"results": None}, {"results": "not-a-list"}],
)
def test_searxng_rejects_malformed_json_payloads(monkeypatch, payload):
    settings = SimpleNamespace(
        searxng_base_url="http://searxng.test",
        search_timeout_seconds=1,
    )
    monkeypatch.setattr(
        "app.services.search.searxng_provider.get_settings",
        lambda: settings,
    )

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload)
            ),
            **kwargs,
        )

    monkeypatch.setattr(
        "app.services.search.searxng_provider.httpx.AsyncClient",
        client_factory,
    )
    provider = SearXNGProvider()

    with pytest.raises(SearchProviderError) as error:
        asyncio.run(provider.search("laptop", 5))

    assert error.value.kind == "malformed_response"


def test_searxng_parses_only_http_results_and_respects_result_limit(monkeypatch):
    settings = SimpleNamespace(
        searxng_base_url="http://searxng.test",
        search_timeout_seconds=1,
    )
    monkeypatch.setattr(
        "app.services.search.searxng_provider.get_settings",
        lambda: settings,
    )
    payload = {
        "results": [
            {
                "title": "First",
                "url": "https://shop.example/product/1",
                "content": "Offer",
                "img_src": "javascript:alert(1)",
            },
            {"title": "Unsafe", "url": "javascript:alert(1)"},
            {"title": "Malformed", "url": "https://[invalid"},
            {"title": "Credential URL", "url": "https://user:secret@shop.example/product"},
            {"title": "Second", "url": "https://shop.example/product/2"},
            {"title": "Third", "url": "https://shop.example/product/3"},
        ]
    }

    original_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return original_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload)
            ),
            **kwargs,
        )

    monkeypatch.setattr(
        "app.services.search.searxng_provider.httpx.AsyncClient",
        client_factory,
    )
    provider = SearXNGProvider()

    results = asyncio.run(provider.search("laptop", 2))

    assert [result.url for result in results] == [
        "https://shop.example/product/1",
        "https://shop.example/product/2",
    ]
    assert results[0].image_url is None


def test_searxng_returns_empty_list_for_valid_empty_response(monkeypatch):
    provider = _provider_for_response(
        monkeypatch,
        lambda request: httpx.Response(200, json={"results": []}),
    )

    assert asyncio.run(provider.search("máy tính", 5)) == []


def test_searxng_maps_timeout_to_provider_error(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("upstream timeout", request=request)

    provider = _provider_for_response(monkeypatch, timeout)

    with pytest.raises(SearchProviderError) as error:
        asyncio.run(provider.search("máy tính", 5))

    assert error.value.kind == "timeout"


def test_searxng_maps_http_error_and_preserves_status(monkeypatch):
    provider = _provider_for_response(
        monkeypatch,
        lambda request: httpx.Response(503, json={"error": "unavailable"}),
    )

    with pytest.raises(SearchProviderError) as error:
        asyncio.run(provider.search("máy tính", 5))

    assert error.value.kind == "http_error"
    assert error.value.status_code == 503
