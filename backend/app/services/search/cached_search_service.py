"""Reuse complete session snapshots without replaying stale offers into the catalog."""

from copy import deepcopy

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.raw_product_candidate import RawProductCandidate
from app.models.recommendation import Recommendation
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.requirement import Requirement
from app.models.search_session import SearchSession
from app.models.source import Source
from app.schemas.search import RawProductCandidateData, SearchExecutionResponse, SearchSourceItem
from app.services.cache.search_cache import DatabaseSearchCache, SearchCache, as_utc, make_cache_key
from app.services.recommendation.recommendation_service import (
    RecommendationRunResult, RecommendationService, requirement_to_schema,
)
from app.services.search.base import SearchProviderError
from app.services.search.search_service import SearchService
from app.services.performance import current_trace


class CachedSearchService:
    """Cache is for new Live sessions; successful-session refreshes stay authoritative."""

    def __init__(self, cache: SearchCache | None = None):
        self.settings = get_settings()
        self.cache = cache if cache is not None else DatabaseSearchCache()

    async def execute(self, *, db: Session, session_id: str, queries: list[str]):
        session = db.get(SearchSession, session_id)
        model = db.scalar(select(Requirement).where(Requirement.session_id == session_id))
        if model is None:
            raise ValueError("Search session has no requirement.")
        requirement = requirement_to_schema(model)
        enabled = not self.settings.demo_mode and self.settings.cache_ttl_seconds > 0
        key = make_cache_key(requirement, scope={
            'retrieval_version': 10,
            'live_search_page_budget_seconds': self.settings.live_search_page_budget_seconds,
            'live_search_domain_budget_seconds': self.settings.live_search_domain_budget_seconds,
            'live_search_target_products': self.settings.live_search_target_products,
            'live_search_min_products': self.settings.live_search_min_products,
            'live_search_max_queries': self.settings.live_search_max_queries,
            'live_search_budget_seconds': self.settings.live_search_budget_seconds,
            'live_search_initial_candidates': self.settings.live_search_initial_candidates,
            'live_search_max_candidates': self.settings.live_search_max_candidates,
            'live_search_discovery_pages': self.settings.live_search_discovery_pages,
            "mode": "live", "search_provider": "tavily", "top_k": self.settings.top_k,
            "max_search_queries": self.settings.max_search_queries,
            "max_results_per_query": self.settings.max_results_per_query,
            "llm_provider": self.settings.llm_provider,
            "llm_fallback_provider": self.settings.llm_fallback_provider,
            "openai_model": self.settings.openai_model, "gemini_model": self.settings.gemini_model,
        })
        has_previous_success = (
            (session is not None and session.completed_at is not None)
            or db.get(RecommendationSnapshot, session_id) is not None
            or db.scalar(select(Recommendation.id).where(Recommendation.session_id == session_id).limit(1)) is not None
        )
        can_reuse = enabled and not has_previous_success
        # An interrupted earlier run may have raw rows without a snapshot.
        # Do not append a second result set to that session.
        can_reuse = can_reuse and db.scalar(select(RawProductCandidate.id).where(
            RawProductCandidate.session_id == session_id,
        ).limit(1)) is None
        if can_reuse:
            cached = self._restore(db, key, session_id, queries, requirement)
            if cached is not None:
                return cached
        try:
            raw = await SearchService().execute(db=db, session_id=session_id, queries=queries)
        except SearchProviderError as exc:
            # Another request may have populated cache while this provider call ran.
            # Never replace a session's previous success on a failed refresh.
            db.rollback()
            if can_reuse:
                cached = self._restore(db, key, session_id, queries, requirement)
                if cached is not None:
                    cached[0].warnings.extend([
                        "Dịch vụ tìm kiếm gặp lỗi; đang dùng cache còn hạn.",
                        *getattr(exc, "warnings", []),
                    ])
                    return cached
            raise
        result = RecommendationService().run(db=db, session_id=session_id)
        # Partial/error results do not replace a healthy cache entry.
        if enabled and not raw.warnings:
            self.cache.put(db, key, db.get(RecommendationSnapshot, session_id), self.settings.cache_ttl_seconds)
        return raw, result

    def _restore(self, db, key, session_id, queries, requirement):
        entry = self.cache.get(db, key)
        if entry is None or entry.session_id == session_id:
            return None
        snapshot = db.get(RecommendationSnapshot, entry.session_id)
        try:
            if snapshot.payload.get("version") != 1:
                return None
            result = TypeAdapter(RecommendationRunResult).validate_python(deepcopy(snapshot.payload["result"]))
        except (KeyError, TypeError, ValidationError):
            return None
        result.requirement = requirement
        result.data_semantics = "snapshot"
        rows = list(db.scalars(select(RawProductCandidate).where(
            RawProductCandidate.session_id == entry.session_id,
        ).order_by(RawProductCandidate.id)))
        raw_products = [RawProductCandidateData.model_validate(row.payload) for row in rows]
        sources = []
        for source_id in dict.fromkeys(row.source_id for row in rows if row.source_id is not None):
            source = db.get(Source, source_id)
            if source is not None:
                sources.append(SearchSourceItem(
                    title=source.title, url=source.url, domain=source.domain,
                    reliability_score=source.reliability_score if source.reliability_score is not None else 50,
                ))
        # Only new-session records are written. Shared products/offers stay untouched.
        for row in rows:
            db.add(RawProductCandidate(
                session_id=session_id, source_id=row.source_id, search_query=row.search_query,
                payload=deepcopy(row.payload), created_at=row.created_at,
            ))
        for item in result.recommendations:
            db.add(Recommendation(
                session_id=session_id, product_id=item.product_id, rank=item.rank,
                **item.score.model_dump(), confidence=item.confidence,
                explanation={
                    "evidence": item.evidence.model_dump(mode="json") if item.evidence else None,
                    "explanation": item.explanation.model_dump(mode="json") if item.explanation else None,
                },
                created_at=snapshot.created_at,
            ))
        db.add(RecommendationSnapshot(
            session_id=session_id, created_at=snapshot.created_at,
            payload={"version": 1, "result": TypeAdapter(RecommendationRunResult).dump_python(result, mode="json")},
        ))
        db.flush()
        raw = SearchExecutionResponse(
            session_id=session_id, queries=queries, sources=sources, raw_products=raw_products,
            total_results=len(rows), total_sources=len(sources), total_products=len(raw_products),
            demo_mode=False,
            warnings=[f"Kết quả từ cache còn hạn; dữ liệu tại {as_utc(snapshot.created_at).isoformat()}."],
        )
        trace = current_trace.get()
        if trace is not None:
            trace.diagnostics.update(cache_hit=True, final_recommendations=len(result.recommendations),
                                     valid_candidates=result.total_found, eligible_offers=result.total_filtered,
                                     stop_reason='snapshot_cache')
        return raw, result
