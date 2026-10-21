"""Fan out queries to every configured, independent web search provider."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.search.base import SearchProvider, SearchProviderError, SearchResult
from app.services.search.searxng_provider import SearXNGProvider
from app.services.search.tavily_provider import TavilyProvider


class MultiSearchProvider(SearchProvider):
    """Query configured providers concurrently and deduplicate by result URL."""

    def __init__(self) -> None:
        settings = get_settings()
        providers: list[SearchProvider] = []
        if settings.tavily_api_key.strip():
            providers.append(TavilyProvider())
        endpoint = settings.searxng_base_url.strip()
        parsed = urlparse(endpoint)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            providers.append(SearXNGProvider())
        self.providers = providers

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        if not self.providers:
            raise SearchProviderError(
                "No live web search provider is configured (set Tavily API key or SearXNG endpoint).",
                kind="not_configured",
            )

        responses = await asyncio.gather(
            *(provider.search(query, max_results) for provider in self.providers),
            return_exceptions=True,
        )
        merged: list[SearchResult] = []
        seen: set[str] = set()
        failures: list[Exception] = []
        for response in responses:
            if isinstance(response, Exception):
                failures.append(response)
                continue
            for result in response:
                if result.url not in seen:
                    seen.add(result.url)
                    merged.append(result)
        if not merged and failures:
            raise SearchProviderError(
                "All configured web search providers failed.", kind="all_providers_failed"
            ) from failures[0]
        return merged[:max_results]