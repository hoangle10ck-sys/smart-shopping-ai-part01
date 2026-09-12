"""Base interfaces for search providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class SearchResult:
    """One raw result returned by a search provider."""

    title: str

    url: str

    content: str = ""

    score: float | None = None

    image_url: str | None = None


class SearchProviderError(RuntimeError):
    """Raised when an external search provider fails."""


class SearchProvider(ABC):
    """Common interface for web search providers."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        """Search the web and return raw results."""