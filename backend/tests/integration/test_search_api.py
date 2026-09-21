"""Integration tests for the search pipeline."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.raw_product_candidate import RawProductCandidate
from app.models.recommendation import Recommendation
from app.models.search_session import SearchSession, SearchSessionStatus
from app.services.search.base import SearchProviderError
from app.services.search.mock_provider import MockSearchProvider


client = TestClient(app)


def test_demo_search_pipeline() -> None:
    """Complete requirement should be searchable in Demo Mode."""

    analyze_response = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": (
                "Tôi có 500 nghìn, "
                "cần tai nghe học online, "
                "mic tốt, pin lâu."
            )
        },
    )

    assert analyze_response.status_code == 200

    analyze_data = analyze_response.json()

    assert (
        analyze_data["needs_clarification"]
        is False
    )

    assert len(
        analyze_data["search_queries"]
    ) >= 1

    session_id = analyze_data["session_id"]

    search_response = client.post(
        "/api/search",
        json={
            "session_id": session_id,
        },
    )

    assert search_response.status_code == 200

    data = search_response.json()

    assert data["session_id"] == session_id
    assert data["demo_mode"] is True
    assert data["total_results"] >= 1
    assert data["total_sources"] >= 1
    assert data["total_products"] >= 1
    assert len(data["raw_products"]) >= 1
    assert data["warnings"] == []


def test_get_persisted_search_result() -> None:
    """GET endpoint should read persisted raw candidates."""

    analyze_response = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": (
                "Tôi có 500 nghìn "
                "cần tai nghe học online "
                "mic tốt pin lâu"
            )
        },
    )

    assert analyze_response.status_code == 200

    session_id = (
        analyze_response.json()["session_id"]
    )

    execute_response = client.post(
        "/api/search",
        json={
            "session_id": session_id,
        },
    )

    assert execute_response.status_code == 200

    get_response = client.get(
        f"/api/search/{session_id}"
    )

    assert get_response.status_code == 200

    data = get_response.json()

    assert data["session_id"] == session_id
    assert data["total_products"] >= 1
    assert len(data["raw_products"]) >= 1


def _analyze_session() -> str:
    response = client.post(
        "/api/requirements/analyze",
        json={"raw_query": "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"},
    )
    assert response.status_code == 200
    assert response.json()["needs_clarification"] is False
    return response.json()["session_id"]


async def _provider_failure(self, query: str, max_results: int):
    raise SearchProviderError("provider unavailable", kind="timeout")


def _stored_results(session_id: str) -> dict:
    """Snapshot persisted rows, not just their counts, across a failed rerun."""
    with SessionLocal() as db:
        return {
            model.__tablename__: [
                {column.name: getattr(row, column.name) for column in model.__table__.columns}
                for row in db.scalars(
                    select(model).where(model.session_id == session_id).order_by(model.id)
                )
            ]
            for model in (RawProductCandidate, Recommendation)
        }


def test_failed_search_rerun_preserves_results_and_warnings(monkeypatch) -> None:
    session_id = _analyze_session()
    success = client.post("/api/search", json={"session_id": session_id})
    assert success.status_code == 200
    before = success.json()
    assert before["recommendations"]
    stored_before = _stored_results(session_id)

    monkeypatch.setattr(MockSearchProvider, "search", _provider_failure)
    failed = client.post("/api/search", json={"session_id": session_id})
    # Assert preservation first so the regression exposes destructive writes.
    assert _stored_results(session_id) == stored_before
    assert failed.status_code == 503
    with SessionLocal() as db:
        assert db.get(SearchSession, session_id).status == SearchSessionStatus.FAILED

    # Separate requests/database sessions must retain both warnings and results.
    with TestClient(app) as reader:
        loaded = reader.get(f"/api/search/{session_id}")
        assert loaded.status_code == 200
        body = loaded.json()
        assert body["status"] == "FAILED"
        assert body["warnings"]
        assert any('[timeout]' in warning for warning in body['warnings'])
        assert failed.json()["detail"] in body["warnings"]
        assert body["recommendations"] == before["recommendations"]
        assert body["raw_products"] == before["raw_products"]
        assert body["processing_time_ms"] == before["processing_time_ms"]
        assert reader.get(f"/api/search/{session_id}").json()["warnings"] == body["warnings"]


def test_first_search_failure_is_readable_without_results(monkeypatch) -> None:
    session_id = _analyze_session()
    monkeypatch.setattr(MockSearchProvider, "search", _provider_failure)
    failed = client.post("/api/search", json={"session_id": session_id})
    assert failed.status_code == 503
    loaded = client.get(f"/api/search/{session_id}")
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "FAILED"
    assert loaded.json()["warnings"]
    assert loaded.json()["recommendations"] == []
    assert loaded.json()["raw_products"] == []
    with SessionLocal() as db:
        session = db.get(SearchSession, session_id)
        assert session.status == SearchSessionStatus.FAILED
        assert session.completed_at is None


def test_successful_retry_clears_failure_warnings(monkeypatch) -> None:
    session_id = _analyze_session()
    with monkeypatch.context() as failing:
        failing.setattr(MockSearchProvider, "search", _provider_failure)
        assert client.post("/api/search", json={"session_id": session_id}).status_code == 503
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["recommendations"]
    assert response.json()["warnings"] == []
    loaded = client.get(f"/api/search/{session_id}").json()
    assert loaded["status"] == "COMPLETED"
    assert loaded["warnings"] == []


@pytest.mark.parametrize("empty_success", [False, True])
def test_partial_search_failure_keeps_success_and_warnings(monkeypatch, empty_success) -> None:
    session_id = _analyze_session()
    original_search = MockSearchProvider.search
    calls = 0

    async def partial_failure(self, query: str, max_results: int):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise SearchProviderError("provider unavailable")
        if empty_success:
            return []
        return await original_search(self, query, max_results)

    monkeypatch.setattr(MockSearchProvider, "search", partial_failure)
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert calls > 1
    assert body["warnings"]
    assert bool(body["recommendations"]) is not empty_success
    loaded = client.get(f"/api/search/{session_id}").json()
    assert loaded["status"] == "COMPLETED"
    assert loaded["warnings"] == body["warnings"]


def test_successful_empty_search_is_not_provider_failure(monkeypatch) -> None:
    session_id = _analyze_session()

    async def empty_search(self, query: str, max_results: int):
        return []

    monkeypatch.setattr(MockSearchProvider, "search", empty_search)
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["recommendations"] == []
    assert response.json()["warnings"] == []
