"""Collector protocol kept separate from URL discovery/search providers."""

from typing import Protocol
from app.schemas.collector import SourceFetchResult


class MarketplaceCollector(Protocol):
    platform: str

    async def fetch(self, url: str) -> SourceFetchResult: ...
