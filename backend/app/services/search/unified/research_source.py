"""Research catalog source for unified search.

Read-only adapter around the existing research evaluate() pipeline. It never
persists raw candidates or offers, keeping the historical dataset policy
(0 ProductOffer created from research records) intact. Research items are
returned as scored recommendations carrying the HISTORICAL_RESEARCH marker.
"""

from __future__ import annotations

from collections import Counter
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research import ResearchProduct
from app.schemas.requirement import RequirementData
from app.services.research.recommendation import evaluate
from app.services.product_images.eligibility import apply_image_eligibility
from app.services.product_images.research import verify_research_images
from app.services.search.unified.base import SourceOutcome

RESEARCH_SOURCE_NAME = "research_catalog"


class ResearchCatalogSource:
    """Expose the historical research catalog inside unified runs."""

    name = RESEARCH_SOURCE_NAME

    def is_available(self, db: Session) -> bool:
        return db.scalar(select(ResearchProduct.id).limit(1)) is not None

    async def search(
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
        checked_count = len(result.recommendations)
        rejection_reasons = await verify_research_images(result.recommendations, db=db)
        rejected = apply_image_eligibility(result, rejection_reasons)
        reason_counts = dict(Counter(rejected.values()))
        outcome.matched_products = len(result.recommendations)
        if rejected:
            outcome.warnings.append(
                f"IMAGE_FILTERED: loại {len(rejected)} sản phẩm vì ảnh thiếu hoặc chưa xác minh được."
            )
            outcome.retrieval_diagnostics.append({
                "image_verification": {
                    "checked": checked_count,
                    "eligible": len(result.recommendations),
                    "rejected_by_reason": reason_counts,
                    "rejected_products": [
                        {"product_id": product_id, "reason": reason}
                        for product_id, reason in sorted(rejected.items())
                    ],
                }
            })
        outcome.research_items = [
            item.model_dump(mode="json") for item in result.recommendations
        ]
        outcome.duration_ms = (time.perf_counter() - started) * 1000
        return outcome
