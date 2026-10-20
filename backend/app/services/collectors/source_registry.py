"""Fail-closed registry for merchant-specific collection permission."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from app.schemas.collector import SourceRegistration


class SourceRegistry:
    def __init__(self, sources: list[SourceRegistration]) -> None:
        by_id: dict[str, SourceRegistration] = {}
        by_domain: dict[str, SourceRegistration] = {}
        for source in sources:
            if source.source_id in by_id:
                raise ValueError(f"duplicate collector source_id: {source.source_id}")
            if source.domain in by_domain:
                raise ValueError(f"duplicate collector domain: {source.domain}")
            by_id[source.source_id] = source
            by_domain[source.domain] = source
        self._by_id = by_id
        self._by_domain = by_domain

    @classmethod
    def from_json(cls, value: str) -> "SourceRegistry":
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("COLLECTOR_SOURCE_REGISTRY_JSON must contain valid JSON") from exc
        if not isinstance(data, list):
            raise ValueError("COLLECTOR_SOURCE_REGISTRY_JSON must be a JSON array")
        return cls([SourceRegistration.model_validate(item) for item in data])

    def get(self, source_id: str) -> SourceRegistration | None:
        return self._by_id.get(source_id)

    def resolve_url(self, url: str) -> SourceRegistration | None:
        try:
            host = (urlsplit(url).hostname or "").rstrip(".").lower()
        except ValueError:
            return None
        exact = self._by_domain.get(host)
        if exact is not None:
            return exact
        matches = [
            source
            for source in self._by_domain.values()
            if source.allow_subdomains and host.endswith("." + source.domain)
        ]
        return matches[0] if len(matches) == 1 else None

    def enabled(self) -> list[SourceRegistration]:
        return [source for source in self._by_id.values() if source.enabled]
