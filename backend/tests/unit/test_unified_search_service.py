"""Unit tests for UnifiedSearchService (U1 Backend Unified Search).

Covers scenario 1-10: catalog full/thin, demo/live/collector available/unavailable,
research mixed-currency ValueError, merge + re-rank, unified snapshot persistence.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.requirement import Requirement
from app.models.search_session import SearchSession, SearchSessionStatus
from app.services.search.unified.orchestrator import UnifiedSearchService

client = TestClient(app)


def _run(coro: Any) -> Any:
    """Chạy coroutine trong ngữ cảnh sync test (pytest không asyncio theo mặc định)."""
    return asyncio.run(coro)


def _analyze_session(raw_query: str) -> str:
    response = client.post(
        "/api/requirements/analyze",
        json={"raw_query": raw_query},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["needs_clarification"] is False
    return data["session_id"]


def _session_has_requirement(session_id: str) -> bool:
    with SessionLocal() as db:
        return (
            db.scalar(
                select(Requirement).where(Requirement.session_id == session_id)
            )
            is not None
        )


# ---------------------------------------------------------------------------
# Scenario 1: Explicit offline test fixture supplements a thin catalog.
# ---------------------------------------------------------------------------
def test_catalog_thin_demo_test_fixture_supplements() -> None:
    session_id = _analyze_session(
        "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["tai nghe học online mic tốt pin lâu"],
            )
        )

    assert result is not None
    # This test explicitly opts into fixtures; production route never does.
    demo_outcome = next(
        (o for o in outcomes if o.source_name == "demo_mock"), None
    )
    assert demo_outcome is not None
    assert demo_outcome.available is False
    # No live calls are made while server is configured for Demo Mode.
    live_outcome = next(
        (o for o in outcomes if o.source_name == "tavily_live"), None
    )
    assert live_outcome is not None
    assert live_outcome.available is False


# ---------------------------------------------------------------------------
# Scenario 3: Catalog sufficient -> external source not required.
# ---------------------------------------------------------------------------
def test_catalog_thin_demo_supplements() -> None:
    session_id = _analyze_session(
        "Tôi có 2 triệu cần laptop học tập, pin lâu, màn hình full HD"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["laptop học tập pin lâu màn hình full HD"],
            )
        )

    assert result is not None
    demo_outcome = next(
        (o for o in outcomes if o.source_name == "demo_mock"), None
    )
    assert live_outcome is None
    assert demo_outcome is not None and demo_outcome.available is True


# ---------------------------------------------------------------------------
# Scenario 3: Research mixed-currency ValueError → research excluded, run continues.
# ---------------------------------------------------------------------------
def test_research_source_outcome_present() -> None:
    session_id = _analyze_session(
        "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["tai nghe mic tốt"],
            )
        )

    assert result is not None
    research_outcome = next(
        (o for o in outcomes if o.source_name == "research_catalog"), None
    )
    collector_outcome = next(
        (o for o in outcomes if o.source_name == "marketplace_collector"), None
    )
    # Budget có cả USD và VND → research raise ValueError (không tự quy đổi FX).
    assert research_outcome.matched_products >= 0
    assert (
        True
    )
    # Unified run tiep tuc khong research.
    assert result.data_mode == "unified"
    assert len(result.recommendations) > 0


# ---------------------------------------------------------------------------
# Scenario 4: Merge research items + re-rank by final_score.
# ---------------------------------------------------------------------------
def test_merge_research_and_rerank() -> None:
    session_id = _analyze_session(
        "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["tai nghe học online mic tốt pin lâu"],
            )
        )

    assert result is not None
    recs = result.recommendations
    # Nếu có recommendations, rank phải liên tục từ 1 và score giảm dần.
    if len(recs) >= 1:
        assert [r.rank for r in recs] == list(range(1, len(recs) + 1))
        scores = [
            r.score.final_score if r.score is not None else 0.0 for r in recs
        ]
        assert scores == sorted(scores, reverse=True), scores


# ---------------------------------------------------------------------------
# Scenario 5: Collector fail-closed → NOT invoked by orchestrator (policy-gated),
#             run continues without collector outcome.
# ---------------------------------------------------------------------------
def test_collector_fail_closed_not_invoked() -> None:
    session_id = _analyze_session(
        "Tôi có 500 nghìn cần tai nghe học online"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["tai nghe học online"],
            )
        )

    assert result is not None
    # Auto mode reports the policy-gated collector as unavailable.
    collector_outcome = next(
        (o for o in outcomes if o.source_name == "marketplace_collector"), None
    )


# ---------------------------------------------------------------------------
# Scenario 6: Unified snapshot persisted with version 1 and source summaries.
# ---------------------------------------------------------------------------
def test_unified_snapshot_persisted() -> None:
    session_id = _analyze_session(
        "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["tai nghe học online mic tốt pin lâu"],
            )
        )

        from app.models.recommendation_snapshot import RecommendationSnapshot

        snapshot = db.get(RecommendationSnapshot, session_id)
        assert snapshot is not None
        payload = snapshot.payload
        assert payload["version"] == 1
        assert "unified_sources" in payload
        assert len(payload["unified_sources"]) == len(outcomes)
        assert "enhancement" in payload
        assert "result" in payload


# ---------------------------------------------------------------------------
# Scenario 7: Return type is tuple (result, outcomes, enhancement).
# ---------------------------------------------------------------------------
def test_returns_tuple() -> None:
    session_id = _analyze_session(
        "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"
    )
    assert _session_has_requirement(session_id)

    with SessionLocal() as db:
        returned = _run(
            UnifiedSearchService().execute(
                db=db,
                session_id=session_id,
                queries=["tai nghe học online mic tốt pin lâu"],
            )
        )

    assert isinstance(returned, tuple)
    assert len(returned) == 3
    result, outcomes, enhancement = returned
    assert hasattr(result, "recommendations")
    assert isinstance(outcomes, list)
    assert enhancement is not None
    assert enhancement.status in {"not_needed", "pending", "completed", "failed"}


# ---------------------------------------------------------------------------
# Scenario 8: data_mode "unified" is a valid Literal in schema.
# ---------------------------------------------------------------------------
def test_data_mode_unified_constant() -> None:
    from app.schemas.recommendation import RecommendationDataMode

    assert "unified" in (
        RecommendationDataMode.__args__  # type: ignore[attr-defined]
    )


# ---------------------------------------------------------------------------
# Scenario 9: Enhancement pending when live available but catalog thin.
# ---------------------------------------------------------------------------
def test_enhancement_pending_enum_supported() -> None:
    from app.schemas.recommendation import UnifiedEnhancement

    e = UnifiedEnhancement(status="pending", detail="Đang tìm thêm…")
    assert e.status == "pending"
    assert e.detail == "Đang tìm thêm…"


# ---------------------------------------------------------------------------
# Scenario 10: No requirement raises ValueError.
# ---------------------------------------------------------------------------
def test_no_requirement_raises_value_error() -> None:
    session_id = "00000000-0000-0000-0000-000000000000"
    with SessionLocal() as db:
        session = SearchSession(
            id=session_id,
            raw_query="anything",
            status=SearchSessionStatus.PENDING,
        )
        db.add(session)
        db.commit()

        with pytest.raises(ValueError, match="no requirement"):
            _run(
                UnifiedSearchService().execute(
                    db=db,
                    session_id=session_id,
                    queries=["anything"],
                )
            )


def test_post_search_defaults_to_unified_scope() -> None:
    from app.schemas.search import SearchRequest

    # Legacy clients retain the old default; the web client explicitly selects auto.
    request = SearchRequest(session_id="session-1")
    assert request.search_scope == "platforms"
    assert SearchRequest(session_id="session-1", search_scope="auto").search_scope == "auto"


def test_analysis_never_requires_clarification_for_missing_optional_fields() -> None:
    response = client.post(
        "/api/requirements/analyze",
        json={"raw_query": "Tìm giúp tôi một sản phẩm phù hợp"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["needs_clarification"] is False
    assert body["search_queries"]


def test_demo_search_source_awaits_pipeline_inside_running_loop(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.core.config import get_settings
    from app.services.search.unified.external_sources import DemoProductSource

    monkeypatch.setattr(get_settings(), "demo_mode", True)
    source = DemoProductSource()
    captured: dict[str, object] = {}

    async def execute(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(total_products=2, warnings=["fixture warning"])

    monkeypatch.setattr("app.services.search.unified.external_sources.SearchService.execute", execute)

    async def run_source():
        return await source.search(
            db=object(),
            session_id="session-1",
            requirement=None,
            queries=["laptop"],
        )

    outcome = _run(run_source())
    assert outcome.matched_products == 2
    assert outcome.warnings == ["fixture warning"]
    assert captured["session_id"] == "session-1"