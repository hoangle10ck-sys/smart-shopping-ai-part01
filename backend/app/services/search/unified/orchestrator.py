"""Unified multi-source search orchestrator.

Coordinates every configured product source, evaluates database freshness,
supplements from external sources only when needed, merges research items
with the main deterministic pipeline, and persists one unified snapshot.
"""

from __future__ import annotations

import logging
import inspect
from datetime import datetime, timezone

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.requirement import Requirement
from app.schemas.recommendation import RecommendationItem, UnifiedEnhancement
from app.services.recommendation.recommendation_service import (
    RecommendationRunResult,
    RecommendationService,
    requirement_to_schema,
)
from app.services.search.unified.base import SourceOutcome
from app.services.search.unified.catalog_source import DatabaseCatalogSource
from app.services.search.unified.external_sources import (
    DemoProductSource,
    LiveProductSource,
    WebDiscoverySource,
)
from app.services.search.unified.research_source import ResearchCatalogSource

logger = logging.getLogger(__name__)


class UnifiedSearchService:
    """Discover and combine every available source for one search session."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.catalog = DatabaseCatalogSource()
        self.research = ResearchCatalogSource()
        self.demo = DemoProductSource()
        self.live = LiveProductSource()
        self.web_discovery = WebDiscoverySource()

    async def execute(
        self,
        *,
        db: Session,
        session_id: str,
        queries: list[str],
        direct_urls: list[str] | None = None,
    ) -> tuple[RecommendationRunResult, list[SourceOutcome], UnifiedEnhancement]:
        """Run the unified pipeline and persist one unified snapshot."""

        model = db.scalar(
            select(Requirement).where(Requirement.session_id == session_id)
        )
        if model is None:
            raise ValueError("Search session has no requirement.")
        requirement = requirement_to_schema(model)

        outcomes: list[SourceOutcome] = []

        # 1. Database catalog replay (synchronous, fast, read-only evidence).
        try:
            catalog_outcome = self.catalog.search(
                db=db, session_id=session_id, requirement=requirement
            )
        except Exception as exc:
            logger.exception("Unified catalog source failed for session %s", session_id)
            db.rollback()
            catalog_outcome = SourceOutcome(
                source_name=self.catalog.name,
                error=f"Catalog search failed: {type(exc).__name__}",
            )
        outcomes.append(catalog_outcome)
        # Persist replay rows before calling an external source that may roll
        # back its own failed pipeline attempt.
        if catalog_outcome.ingested_rows:
            db.commit()

        # 2. Research catalog (read-only; never creates offers).
        try:
            research_result = self.research.search(
                db=db, session_id=session_id, requirement=requirement
            )
            research_outcome = (
                await research_result
                if inspect.isawaitable(research_result)
                else research_result
            )
        except Exception as exc:
            logger.exception("Unified research source failed for session %s", session_id)
            db.rollback()
            research_outcome = SourceOutcome(
                source_name=self.research.name,
                error=f"Research catalog search failed: {type(exc).__name__}",
                warnings=["Research catalog is unavailable for this search."],
            )
        outcomes.append(research_outcome)

        # SearXNG is discovery-only: its URLs are returned as unverified
        # candidates and never enter the product-page fetch or persistence path.
        # Keep partially constructed service instances used by legacy callers
        # and focused tests compatible while normal instances initialize the
        # discovery source in __init__.
        web_discovery = getattr(self, "web_discovery", None) or WebDiscoverySource()
        if web_discovery.is_available(db):
            try:
                discovery_outcome = await web_discovery.search(
                    db=db,
                    session_id=session_id,
                    requirement=requirement,
                    queries=queries,
                )
            except Exception as exc:
                logger.exception("Unified web discovery failed for session %s", session_id)
                discovery_outcome = SourceOutcome(
                    source_name=web_discovery.name,
                    available=False,
                    error=f"SearXNG discovery failed: {type(exc).__name__}",
                    warnings=["Web discovery is unavailable; other results are retained."],
                )
            outcomes.append(discovery_outcome)

        # 3. Always inspect every configured external source for this run.
        # A sufficiently populated local catalog is not proof that its offers
        # are current or that it contains the best available alternatives.
        enhancement = UnifiedEnhancement(status="not_needed")
        # Unified shopping recommendations must never ingest Demo fixtures as
        # catalog offers. The legacy Demo adapter is intentionally not called.
        # A user-supplied product URL is an independent source: it must still
        # be fetched through the collector when web discovery has no provider.
        # The collector enforces its own permission and access policy.
        if self.live.is_available(db) or direct_urls:
            try:
                live_outcome = await self.live.search(
                    db=db,
                    session_id=session_id,
                    requirement=requirement,
                    queries=queries,
                    direct_urls=direct_urls,
                )
            except Exception as exc:
                logger.exception("Unified live source failed for session %s", session_id)
                db.rollback()
                live_outcome = SourceOutcome(
                    source_name=self.live.name,
                    error=f"Live search failed: {type(exc).__name__}",
                    warnings=["Online source failed; other available results are retained."],
                )
            outcomes.append(live_outcome)
            if live_outcome.error:
                enhancement = UnifiedEnhancement(
                    status="failed",
                    detail="Không thể bổ sung dữ liệu trực tuyến trong lần tìm này.",
                )
            else:
                if live_outcome.ingested_rows:
                    db.commit()
                enhancement = UnifiedEnhancement(status="completed")
        else:
            outcomes.append(SourceOutcome(
                source_name=self.live.name,
                available=False,
                error=(
                    "Chưa cấu hình nguồn tìm kiếm trực tuyến "
                    "(Tavily API key)."
                ),
            ))

        # 4. Run deterministic recommendation and merge read-only research rows.

        # 4. Chạy pipeline gợi ý xác định trên candidate đã replay + live;
        #    hợp nhất research_items, re-rank theo final_score.
        recommendation_service = RecommendationService()
        result = recommendation_service._evaluate(
            db=db, session_id=session_id, persist=False
        )

        merged: list[RecommendationItem] = list(result.recommendations)
        for item_data in research_outcome.research_items:
            research_item = RecommendationItem.model_validate(item_data)
            # Đánh dấu nguồn nghiên cứu (read-only, không tạo offer).
            research_item.source_mode = "HISTORICAL_RESEARCH"
            merged.append(research_item)

        # Re-rank theo final_score giảm dần; ổn định khi bằng điểm.
        merged.sort(
            key=lambda r: (
                r.score.final_score if r.score is not None else 0.0,
                -(r.product_id or 0),
            ),
            reverse=True,
        )
        for idx, rec in enumerate(merged, start=1):
            rec.rank = idx

        result.recommendations = merged
        result.total_found = max(result.total_found, len(merged))
        result.total_filtered = max(result.total_filtered, len(merged))
        result.data_mode = "unified"
        merged = merged[: self.settings.unified_top_k]
        result.recommendations = merged
        for idx, rec in enumerate(merged, start=1):
            rec.rank = idx
        # _evaluate runs read-only here, but this result becomes the persisted
        # session snapshot and must be labelled with snapshot semantics.
        result.data_semantics = "snapshot"
        recommendation_service.persist_snapshot_rows(
            db=db, session_id=session_id, result=result
        )

        # 5. Persist the unified snapshot in the current unit of work. The API
        # route commits the snapshot together with the terminal session status.
        snapshot = db.get(RecommendationSnapshot, session_id)
        if snapshot is None:
            snapshot = RecommendationSnapshot(session_id=session_id)
            db.add(snapshot)
        snapshot.payload = {
            "version": 1,
            "data_mode": "unified",
            "unified_sources": [o.summary() for o in outcomes],
            "retrieval_diagnostics": [
                diagnostic
                for outcome in outcomes
                for diagnostic in outcome.retrieval_diagnostics
            ],
            "enhancement": enhancement.model_dump(mode="json"),
            "result": TypeAdapter(RecommendationRunResult).dump_python(
                result, mode="json"
            ),
        }
        snapshot.created_at = datetime.now(timezone.utc)
        db.flush()

        return result, outcomes, enhancement
