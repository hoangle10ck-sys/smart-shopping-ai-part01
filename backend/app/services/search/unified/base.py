"""Unified multi-source search: protocol and shared outcome types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SourceOutcome:
    """Report one source's contribution to a unified search run."""

    source_name: str
    available: bool = True
    matched_products: int = 0
    fresh_products: int = 0
    ingested_rows: int = 0
    research_items: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0

    def summary(self) -> dict:
        """Serialisable summary persisted in the snapshot and API response."""
        return {
            "source": self.source_name,
            "available": self.available,
            "matched_products": self.matched_products,
            "fresh_products": self.fresh_products,
            "ingested_rows": self.ingested_rows,
            "research_items": len(self.research_items),
            "warnings": list(self.warnings),
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }
