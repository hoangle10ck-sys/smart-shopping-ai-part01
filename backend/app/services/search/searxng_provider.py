"""Search provider for an operator-configured SearXNG instance."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.services.search.base import SearchProvider, SearchProviderError, SearchResult


def _valid_http_url(value: object) -> str | None:
    """Accept only absolute HTTP(S) URLs without embedded credentials."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlparse(value)
        # Accessing .port also validates malformed or out-of-range ports.
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return value


class SearXNGProvider(SearchProvider):
    """Use only the explicitly configured SearXNG endpoint (never public instances)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.searxng_base_url.strip().rstrip("/")
        self.timeout = settings.search_timeout_seconds
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SearchProviderError("SearXNG endpoint is not configured.", kind="not_configured")

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params={"q": query, "format": "json", "language": "all"},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise SearchProviderError("SearXNG request timed out.", kind="timeout") from exc
        except httpx.HTTPStatusError as exc:
            raise SearchProviderError(
                f"SearXNG returned HTTP {exc.response.status_code}.",
                kind="http_error",
                status_code=exc.response.status_code,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchProviderError("SearXNG network or response error.", kind="provider_error") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise SearchProviderError(
                "SearXNG returned a malformed response.",
                kind="malformed_response",
            )

        results: list[SearchResult] = []
        for item in payload["results"]:
            if not isinstance(item, dict):
                continue
            title, url = item.get("title"), item.get("url")
            safe_url = _valid_http_url(url)
            if isinstance(title, str) and safe_url is not None:
                results.append(
                    SearchResult(
                        title=title,
                        url=safe_url,
                        content=str(item.get("content") or ""),
                        score=item.get("score") if isinstance(item.get("score"), (int, float)) else None,
                        image_url=_valid_http_url(item.get("img_src")),
                    )
                )
                if len(results) >= max_results:
                    break
        return results
