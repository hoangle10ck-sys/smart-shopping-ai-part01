"""History uses existing sessions and snapshots, including failed attempts."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.product_offer import ProductOffer
from app.models.search_session import SearchSession, SearchSessionStatus
from app.services.search.mock_provider import MockSearchProvider
from sqlalchemy import select


def test_empty_history():
    with TestClient(app) as client:
        response = client.get("/api/history")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_multiple_sessions_newest_first_with_pagination():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with SessionLocal() as db:
        for day, status in enumerate([SearchSessionStatus.PENDING, SearchSessionStatus.FAILED, SearchSessionStatus.COMPLETED]):
            db.add(SearchSession(raw_query=f"Query {day}", status=status, created_at=now + timedelta(days=day)))
        db.commit()
    with TestClient(app) as client:
        response = client.get("/api/history?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert [item["raw_query"] for item in body["items"]] == ["Query 2", "Query 1"]
        assert body["items"][1]["status"] == "FAILED"
        assert body["items"][0]["created_at"].endswith("Z")
        assert client.get("/api/history?offset=2").json()["items"][0]["raw_query"] == "Query 0"
        assert client.get("/api/history?limit=101").status_code == 422


def test_unknown_session_is_404():
    with TestClient(app) as client:
        assert client.get("/api/history/missing").status_code == 404


def test_pending_session_without_requirement_has_readable_detail():
    with SessionLocal() as db:
        session = SearchSession(raw_query="Chưa phân tích")
        db.add(session)
        db.commit()
        session_id = session.id
    with TestClient(app) as client:
        response = client.get(f"/api/history/{session_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING"
        assert response.json()["result"] is None


def test_history_detail_uses_snapshot_even_after_offer_changes_and_failed_rerun(monkeypatch):
    with TestClient(app) as client:
        analyzed = client.post("/api/requirements/analyze", json={"raw_query": "Tai nghe 500 nghìn học online mic tốt"})
        session_id = analyzed.json()["session_id"]
        original = client.post("/api/search", json={"session_id": session_id}).json()
        with SessionLocal() as db:
            for offer in db.scalars(select(ProductOffer)):
                offer.price = 9999999
            db.commit()

        async def fail(*args, **kwargs):
            raise RuntimeError("Provider unavailable")

        monkeypatch.setattr(MockSearchProvider, "search", fail)
        assert client.post("/api/search", json={"session_id": session_id}).status_code == 503
        response = client.get(f"/api/history/{session_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "FAILED"
        assert body["result"]["data_semantics"] == "snapshot"
        assert body["result"]["recommendations"] == original["recommendations"]
        assert body["result"]["warnings"]
        assert body["result"] == client.get(f"/api/search/{session_id}").json()
        item = client.get("/api/history").json()["items"][0]
        assert item["recommendation_count"] == len(original["recommendations"])
        assert item["status"] == "FAILED"
