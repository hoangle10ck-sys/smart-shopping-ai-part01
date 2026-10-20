"""Unified multi-source search orchestrator.

Coordinates every configured product source, evaluates database freshness,
supplements from external sources only when needed, merges research items
with the main deterministic pipeline, and persists one unified snapshot.
"""

from __future__ import annotations

import logging
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
    CollectorProductSource,
    DemoProductSource,
    LiveProductSource,
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
        self.collector = CollectorProductSource()

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
        catalog_outcome = self.catalog.search(
            db=db, session_id=session_id, requirement=requirement
        )
        outcomes.append(catalog_outcome)
        # Persist replay rows before any pipeline that starts with rollback().
        db.commit()

        # 2. Research catalog (read-only; never creates offers).
        research_outcome = self.research.search(
            db=db, session_id=session_id, requirement=requirement
        )
        outcomes.append(research_outcome)

        # 3. External supplement only when the internal catalog is thin.
        need_external = (
            catalog_outcome.fresh_products < self.settings.unified_min_fresh_products
        )
        enhancement = UnifiedEnhancement(status="not_needed")
        if need_external:
            # Demo fixtures must never be presented as commercial offers.
            if self.settings.demo_mode:
                outcomes.append(SourceOutcome(
                    source_name=self.demo.name,
                    available=False,
                    error="Dữ liệu minh họa bị loại khỏi kết quả mua sắm unified.",
                ))
            elif self.live.is_available(db):
                live_outcome = await self.live.search(
                    db=db,
                    session_id=session_id,
                    requirement=requirement,
                    queries=queries,
                    direct_urls=direct_urls,
                )
                outcomes.append(live_outcome)
                if live_outcome.error:
                    enhancement = UnifiedEnhancement(
                        status="failed",
                        detail="Không thể bổ sung dữ liệu trực tuyến trong lần tìm này.",
                    )
                else:
                    db.commit()
                    enhancement = UnifiedEnhancement(status="completed")
            else:
                outcomes.append(SourceOutcome(
                    source_name=self.live.name,
                    available=False,
                    error="Không có nguồn live khả dụng (Demo mode hoặc thiếu Tavily key).",
                ))
        else:
            outcomes.append(SourceOutcome(
                source_name=self.live.name,
                available=False,
                warnings=[
                    f"Catalog nội bộ đủ {catalog_outcome.fresh_products} sản phẩm mới; "
                    "không cần truy vấn nguồn trực tuyến."
                ],
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
        result.total_recommended = len(merged)
        for idx, rec in enumerate(merged, start=1):
            rec.rank = idx

        # 5. Lưu unified RecommendationSnapshot, commit, trả về tuple.
        snapshot = db.get(RecommendationSnapshot, session_id)
        if snapshot is None:
            snapshot = RecommendationSnapshot(session_id=session_id)
            db.add(snapshot)
        snapshot.payload = {
            "version": 1,
            "unified_sources": [o.summary() for o in outcomes],
            "enhancement": enhancement.model_dump(mode="json"),
            "result": TypeAdapter(RecommendationRunResult).dump_python(
                result, mode="json"
            ),
        }
        snapshot.created_at = datetime.now(timezone.utc)
        db.commit()

        return result, outcomes, enhancement
