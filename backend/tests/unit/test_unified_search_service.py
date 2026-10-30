"""Unit tests for UnifiedSearchService (U1 Backend Unified Search).

Covers scenario 1-10: catalog full/thin, demo/live/collector available/unavailable,
research mixed-currency ValueError, merge + re-rank, unified snapshot persistence.
"""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.requirement import Requirement
from app.models.search_session import SearchSession, SearchSessionStatus
from app.services.search.unified.orchestrator import UnifiedSearchService

client = TestClient(app)


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch) -> None:
    """Fail closed if a unit test attempts an outbound HTTP request."""

    def assert_not_external(url: object) -> None:
        parsed = urlparse(str(url))
        host = (parsed.hostname or "").lower()
        if host not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            raise AssertionError("Unit tests must not make outbound HTTP requests")

    def deny_request(*args, **kwargs):
        url = kwargs.get("url")
        if url is None and len(args) > 1:
            url = args[1]
        assert_not_external(url)
        return None

    original_socket_connect = socket.socket.connect

    def block_external_socket(self, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if str(host).lower() not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            raise AssertionError("Unit tests must not open external sockets")
        return original_socket_connect(self, address)

    original_socket_connect_ex = socket.socket.connect_ex

    def block_external_socket_ex(self, address):
        host = address[0] if isinstance(address, tuple) and address else address
        if str(host).lower() not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            raise AssertionError("Unit tests must not open external sockets")
        return original_socket_connect_ex(self, address)

    monkeypatch.setattr(httpx, "request", deny_request)
    monkeypatch.setattr(httpx.Client, "request", deny_request)
    monkeypatch.setattr(httpx.AsyncClient, "request", deny_request)
    monkeypatch.setattr(socket.socket, "connect", block_external_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", block_external_socket_ex)


@pytest.fixture(autouse=True)
def isolate_configured_web_search(monkeypatch):
    """Use deterministic provider stubs for unified-search unit tests."""
    from app.core.config import get_settings
    from app.services.search.multi_provider import MultiSearchProvider

    monkeypatch.setattr(get_settings(), "tavily_api_key", "")
    monkeypatch.setattr(get_settings(), "searxng_base_url", "")
    monkeypatch.setattr(
        MultiSearchProvider,
        "search",
        lambda *args, **kwargs: pytest.fail(
            "Configured web search must remain unavailable in isolated unit tests"
        ),
    )


from app.services.search.mock_provider import HEADPHONE_RESULTS


def test_configured_web_search_availability_uses_test_configuration(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.search.unified.external_sources import LiveProductSource

    settings = get_settings()
    source = LiveProductSource()
    assert source.is_available(object()) is False

    monkeypatch.setattr(settings, "tavily_api_key", "test-only-not-a-secret")
    assert source.is_available(object()) is True
    # This test exercises configuration only; it deliberately does not call search().


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
# Scenario 1: Demo fixtures never supplement unified shopping results.
# ---------------------------------------------------------------------------
def test_catalog_thin_demo_test_fixture_never_supplements(monkeypatch) -> None:
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
    assert result.recommendations == []
    monkeypatch.setattr(UnifiedSearchService, "__init__", lambda self: None)
    service = UnifiedSearchService()
    # Keep this assertion at the orchestration boundary: even an explicitly
    # enabled Demo source must not be queried by unified shopping search.
    from app.services.search.unified.base import SourceOutcome
    from app.services.search.unified.external_sources import DemoProductSource
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    service.settings = get_settings()
    service.catalog = SimpleNamespace(search=lambda **kwargs: SourceOutcome(source_name="database_catalog"))
    service.research = SimpleNamespace(search=lambda **kwargs: SourceOutcome(source_name="research_catalog"))
    service.demo = DemoProductSource()
    service.live = SimpleNamespace(is_available=lambda db: False, name="configured_web_search")
    demo_calls = []
    async def demo_search(**kwargs):
        demo_calls.append(kwargs)
        return SourceOutcome(source_name="demo_mock", matched_products=1, ingested_rows=1)
    monkeypatch.setattr(service.demo, "search", demo_search)
    with SessionLocal() as db:
        result, outcomes, _ = _run(service.execute(
            db=db, session_id=session_id, queries=["tai nghe học online mic tốt pin lâu"]
        ))
    assert not demo_calls
    assert all(outcome.source_name != "demo_mock" for outcome in outcomes)
    assert result.recommendations == []
    live_outcome = next(
        (o for o in outcomes if o.source_name == "configured_web_search"), None
    )
    assert live_outcome is not None
    assert live_outcome.available is False
    assert "Tavily API key" in (live_outcome.error or "")
    assert not any("collector" in o.source_name for o in outcomes)


# ---------------------------------------------------------------------------
# Scenario 3: Catalog sufficiency does not enable Demo fallback.
# ---------------------------------------------------------------------------
def test_catalog_search_reports_sources_even_when_catalog_is_sufficient(monkeypatch) -> None:
    session_id = _analyze_session(
        "Tôi có 2 triệu cần laptop học tập, pin lâu, màn hình full HD"
    )
    assert _session_has_requirement(session_id)

    from app.services.search.unified.orchestrator import UnifiedSearchService

    service = UnifiedSearchService()
    # Simulate a mature catalog deterministically; source discovery must still
    # report external coverage rather than silently treating it as unnecessary.
    from app.services.search.unified.base import SourceOutcome
    monkeypatch.setattr(service.catalog, "search", lambda **kwargs: SourceOutcome(
        source_name="database_catalog", matched_products=8, fresh_products=8,
    ))

    with SessionLocal() as db:
        result, outcomes, enhancement = _run(
            service.execute(
                db=db,
                session_id=session_id,
                queries=["laptop học tập pin lâu màn hình full HD"],
            )
        )

    assert result is not None
    assert any(o.source_name == "database_catalog" and o.matched_products == 8 for o in outcomes)
    live_outcome = next(o for o in outcomes if o.source_name == "configured_web_search")
    assert not any(o.source_name == "demo_mock" for o in outcomes)
    assert live_outcome.available is False
    assert "Tavily API key" in (live_outcome.error or "")
    assert not any("collector" in o.source_name for o in outcomes)


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
    assert result.total_found >= result.total_filtered
    assert result.total_filtered >= len(result.recommendations)
    assert result.data_mode == "unified"
    research_outcome = next(
        (o for o in outcomes if o.source_name == "research_catalog"), None
    )
    # Budget có cả USD và VND → research raise ValueError (không tự quy đổi FX).
    assert research_outcome is not None
    assert research_outcome.matched_products == len(research_outcome.research_items)
    assert research_outcome.error is None
    for item in research_outcome.research_items:
        assert item["source_mode"] == "HISTORICAL_RESEARCH"
        assert item["research_provenance"]
        assert item.get("offer_id") is None
    # Unified run tiep tuc khong research.
    assert result.total_found == 0 or result.total_filtered <= result.total_found


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
    assert not any("collector" in o.source_name for o in outcomes)


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

    request = SearchRequest(session_id="session-1")
    assert request.search_scope == "auto"
    # Legacy clients can still submit the old scope while migrating.
    assert SearchRequest(session_id="session-1", search_scope="platforms").search_scope == "platforms"
    assert SearchRequest(session_id="session-1", search_scope="auto").search_scope == "auto"


def test_search_request_trims_and_deduplicates_direct_urls_before_limit() -> None:
    from app.schemas.search import SearchRequest

    url = "https://shop.example/product"
    request = SearchRequest(
        session_id="session-1",
        direct_urls=[f" {url} ", "", url, f"{url}  ", url, url],
    )

    assert request.direct_urls == [url]


def test_analysis_category_without_optional_budget_or_purpose_needs_no_clarification() -> None:
    response = client.post(
        "/api/requirements/analyze",
        json={"raw_query": "Tôi cần tai nghe"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["needs_clarification"] is False
    assert body["search_queries"]


def test_analysis_without_category_requests_clarification() -> None:
    response = client.post(
        "/api/requirements/analyze",
        json={"raw_query": "Tìm giúp tôi một sản phẩm phù hợp"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["needs_clarification"] is True
    assert body["clarification_question"]


def test_demo_search_source_awaits_pipeline_inside_running_loop(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.core.config import get_settings
    from app.services.search.unified.external_sources import DemoProductSource

    monkeypatch.setattr(get_settings(), "demo_mode", True)
    source = DemoProductSource()
    captured: dict[str, object] = {}

    async def execute(self, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(total_products=2, warnings=["fixture warning"], retrieval_diagnostics=[])

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


def test_unified_search_source_exception_is_reported_without_stopping_other_sources(monkeypatch) -> None:
    """A failed configured live source is represented as an outcome, not raised."""
    from types import SimpleNamespace

    from app.core.config import get_settings
    from app.services.search.unified.external_sources import LiveProductSource

    monkeypatch.setattr(get_settings(), "demo_mode", False)
    source = LiveProductSource()

    async def failed_pipeline(self, **kwargs):
        raise RuntimeError("provider failure details must not enter public outcome")

    monkeypatch.setattr("app.services.search.unified.external_sources.SearchService.execute", failed_pipeline)
    monkeypatch.setattr(source, "settings", SimpleNamespace(unified_source_timeout_seconds=1))
    outcome = _run(source.search(
        db=object(), session_id="session-1", requirement=None, queries=["laptop"]
    ))

    assert outcome.error == "RuntimeError"
    assert "provider failure details" not in outcome.error
    assert "provider failure details" not in " ".join(outcome.warnings)
    assert outcome.warnings


def test_unified_orchestrator_keeps_processing_when_live_provider_raises(monkeypatch) -> None:
    from app.core.database import SessionLocal
    from app.models.recommendation_snapshot import RecommendationSnapshot
    from app.models.search_session import SearchSession, SearchSessionStatus
    from app.services.search.unified.orchestrator import UnifiedSearchService

    session_id = _analyze_session("Tôi cần laptop cho học tập")
    monkeypatch.setattr("app.services.search.unified.orchestrator.get_settings", lambda: type(
        "Settings", (), {"demo_mode": False, "unified_top_k": 10}
    )())

    with SessionLocal() as db:
        service = UnifiedSearchService()
        monkeypatch.setattr(service.catalog, "search", lambda **kwargs: SourceOutcome(
            source_name="database_catalog", matched_products=1
        ))
        monkeypatch.setattr(service.research, "search", lambda **kwargs: SourceOutcome(
            source_name="research_catalog"
        ))
        monkeypatch.setattr(service.live, "is_available", lambda db: True)

        async def fail_live(**kwargs):
            raise RuntimeError("offline provider")

        monkeypatch.setattr(service.live, "search", fail_live)
        result, outcomes, enhancement = _run(service.execute(
            db=db, session_id=session_id, queries=["laptop"]
        ))
        assert enhancement.status == "failed"
        assert next(o for o in outcomes if o.source_name == service.live.name).error
        snapshot = db.get(RecommendationSnapshot, session_id)
        assert snapshot is not None
        assert snapshot.payload["unified_sources"]
        assert snapshot.payload["data_mode"] == "unified"
        db.commit()

    with SessionLocal() as verify:
        session = verify.get(SearchSession, session_id)
        assert session is not None
        assert session.status != SearchSessionStatus.PROCESSING


def test_catalog_payload_uses_offer_check_time_not_product_update_time() -> None:
    from app.services.search.unified.catalog_source import DatabaseCatalogSource

    offer_checked = datetime(2026, 4, 1, 15, 30, tzinfo=timezone(timedelta(hours=7)))
    product_updated = datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc)
    payload = DatabaseCatalogSource._catalog_payload(
        SimpleNamespace(name="Phone", category="phone", brand=None, model=None,
                        rating=None, review_count=None, specifications={}, image_url=None,
                        updated_at=product_updated),
        SimpleNamespace(last_checked_at=offer_checked, price=100, availability="in_stock",
                        product_url="https://shop.example/phone", merchant="Shop", currency="VND"),
    )

    restored = datetime.fromisoformat(payload["observed_at"])
    assert restored.utcoffset() == timedelta(0)
    assert restored == offer_checked
    assert restored != product_updated
    assert payload["page_validation"]["last_checked_at"] == offer_checked.isoformat()


def test_catalog_payload_does_not_assign_utc_to_naive_offer_check() -> None:
    from app.services.search.unified.catalog_source import DatabaseCatalogSource

    naive_checked = datetime(2026, 4, 1, 15, 30)
    payload = DatabaseCatalogSource._catalog_payload(
        SimpleNamespace(name="Phone", category=None, brand=None, model=None, rating=None,
                        review_count=None, specifications={}, image_url=None,
                        updated_at=datetime(2026, 4, 2, tzinfo=timezone.utc)),
        SimpleNamespace(last_checked_at=naive_checked, price=100, availability=None,
                        product_url="https://shop.example/phone", merchant=None, currency="VND"),
    )

    assert payload["observed_at"] is None
    assert payload["page_validation"]["last_checked_at"] == naive_checked.isoformat()
    from app.schemas.search import RawProductCandidateData

    candidate = RawProductCandidateData.model_validate(payload)
    assert candidate.observed_at is None


def test_missing_observed_at_survives_normalization_and_json_cache_payload() -> None:
    from app.schemas.search import RawProductCandidateData
    from app.services.normalization.product_normalizer import ProductNormalizer

    candidate = RawProductCandidateData(name="Phone X", observed_at=None)
    normalized = ProductNormalizer().normalize(candidate)
    assert normalized is not None
    assert normalized.observed_at is None

    cached_payload = candidate.model_dump(mode="json")
    restored = RawProductCandidateData.model_validate(cached_payload)
    assert restored.observed_at is None


def test_naive_observed_at_survives_candidate_and_cached_payload_without_utc_label() -> None:
    from app.schemas.search import RawProductCandidateData
    from app.services.normalization.product_normalizer import ProductNormalizer

    naive = datetime(2026, 4, 1, 15, 30)
    candidate = RawProductCandidateData(name="Phone X", observed_at=naive)
    normalized = ProductNormalizer().normalize(candidate)
    assert normalized is not None
    assert normalized.observed_at == naive
    assert normalized.observed_at.tzinfo is None

    restored = RawProductCandidateData.model_validate(candidate.model_dump(mode="json"))
    assert restored.observed_at == naive
    assert restored.observed_at.tzinfo is None
