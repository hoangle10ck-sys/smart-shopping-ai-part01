"""Tests for configured multi-provider fan-out."""

import asyncio
from types import SimpleNamespace

from app.core.config import Settings
from app.services.search.base import SearchResult
from app.services.search.multi_provider import MultiSearchProvider


def test_multi_provider_includes_only_configured_providers(monkeypatch):
    settings = SimpleNamespace(
        tavily_api_key="key",
        searxng_base_url="https://search.local",
        search_timeout_seconds=15,
        search_retry_count=0,
    )
    monkeypatch.setattr("app.services.search.multi_provider.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.search.tavily_provider.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.search.searxng_provider.get_settings", lambda: settings)
    provider = MultiSearchProvider()
    assert len(provider.providers) == 2


def test_product_ingestion_pipeline_can_exclude_discovery_only_searxng(monkeypatch):
    settings = SimpleNamespace(
        tavily_api_key="key",
        searxng_base_url="http://searxng:8080",
        search_timeout_seconds=15,
        search_retry_count=0,
    )
    monkeypatch.setattr("app.services.search.multi_provider.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.search.tavily_provider.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.search.searxng_provider.get_settings", lambda: settings)

    provider = MultiSearchProvider(include_searxng=False)

    assert len(provider.providers) == 1
    assert provider.providers[0].__class__.__name__ == "TavilyProvider"


def test_multi_provider_merges_and_deduplicates_results(monkeypatch):
    settings = SimpleNamespace(
        tavily_api_key="key",
        searxng_base_url="https://search.local",
        search_timeout_seconds=15,
        search_retry_count=0,
    )
    monkeypatch.setattr("app.services.search.multi_provider.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.search.tavily_provider.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.search.searxng_provider.get_settings", lambda: settings)
    provider = MultiSearchProvider()

    class FixtureProvider:
        def __init__(self, results):
            self.results = results

        async def search(self, query, max_results):
            return self.results

    provider.providers = [
        FixtureProvider([SearchResult("one", "https://example.test/1")]),
        FixtureProvider([SearchResult("one duplicate", "https://example.test/1"),
                         SearchResult("two", "https://example.test/2")]),
    ]
    results = asyncio.run(provider.search("query", 10))
    assert [item.url for item in results] == ["https://example.test/1", "https://example.test/2"]
