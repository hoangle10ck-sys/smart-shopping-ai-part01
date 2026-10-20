"""Research catalog source for unified search.

Read-only adapter around the existing research evaluate() pipeline. It never
persists raw candidates or offers, keeping the historical dataset policy
(0 ProductOffer created from research records) intact. Research items are
returned as scored recommendations carrying the HISTORICAL_RESEARCH marker.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research import ResearchProduct
from app.schemas.requirement import RequirementData
from app.services.research.recommendation import evaluate
from app.services.search.unified.base import SourceOutcome

RESEARCH_SOURCE_NAME = "research_catalog"


class ResearchCatalogSource:
    """Expose the historical research catalog inside unified runs."""

    name = RESEARCH_SOURCE_NAME

    def is_available(self, db: Session) -> bool:
        return db.scalar(select(ResearchProduct.id).limit(1)) is not None

    def search(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
    ) -> SourceOutcome:
        started = time.perf_counter()
        outcome = SourceOutcome(source_name=self.name)

        try:
            result, warnings = evaluate(db, requirement)
        except ValueError as exc:
            # Mixed currency / decimal budget: research stays out of this run.
            outcome.error = str(exc)
            outcome.duration_ms = (time.perf_counter() - started) * 1000
            return outcome

        outcome.warnings.extend(warnings)
        outcome.matched_products = len(result.recommendations)
        outcome.research_items = [
            item.model_dump(mode="json") for item in result.recommendations
        ]
        outcome.duration_ms = (time.perf_counter() - started) * 1000
        return outcome
