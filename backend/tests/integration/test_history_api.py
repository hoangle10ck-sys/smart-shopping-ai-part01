"""History uses existing sessions and snapshots, including failed attempts."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.product_offer import ProductOffer
from app.models.search_session import SearchSession, SearchSessionStatus
from app.services.search.unified.external_sources import LiveProductSource
from sqlalchemy import select
from tests.fixtures.unified_catalog import seed_headphones


def test_empty_history():
    with TestClient(app) as client:
        response = client.get("/api/history")
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_multiple_sessions_newest_first_with_pagination():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with TestClient(app) as client:
        session_ids = []
        for day in range(3):
            analyzed = client.post(
                "/api/requirements/analyze",
                json={"raw_query": f"Tai nghe cho học online Query {day}"},
            )
            assert analyzed.status_code == 200, analyzed.text
            session_ids.append(analyzed.json()["session_id"])
        with SessionLocal() as db:
            for day, (session_id, state) in enumerate(zip(
                session_ids,
                [SearchSessionStatus.PENDING, SearchSessionStatus.FAILED, SearchSessionStatus.COMPLETED],
            )):
                session = db.get(SearchSession, session_id)
                session.status = state
                session.created_at = now + timedelta(days=day)
            db.commit()

        response = client.get("/api/history?limit=2")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert [item["raw_query"] for item in body["items"]] == [
            "Tai nghe cho học online Query 2",
            "Tai nghe cho học online Query 1",
        ]
        assert body["items"][1]["status"] == "FAILED"
        assert body["items"][0]["created_at"].endswith("Z")
        assert client.get("/api/history?offset=2").json()["items"][0]["raw_query"] == "Tai nghe cho học online Query 0"
        assert client.get("/api/history?limit=101").status_code == 422


def test_unknown_session_is_404():
    with TestClient(app) as client:
        assert client.get("/api/history/missing").status_code == 404


def test_guest_history_and_session_results_are_isolated_between_browsers():
    with TestClient(app) as owner_client:
        analyzed = owner_client.post(
            "/api/requirements/analyze",
            json={"raw_query": "Tai nghe cho học online"},
        )
        assert analyzed.status_code == 200, analyzed.text
        session_id = analyzed.json()["session_id"]
        cookie = owner_client.cookies.get("shopping_guest")
        assert cookie

        own_history = owner_client.get(f"/api/history/{session_id}")
        assert own_history.status_code == 200
        assert own_history.json()["session_id"] == session_id

    with TestClient(app) as stranger_client:
        stranger_history = stranger_client.get("/api/history")
        assert stranger_history.status_code == 200
        assert stranger_history.json()["total"] == 0
        assert stranger_client.get(f"/api/history/{session_id}").status_code == 404
        assert stranger_client.get(f"/api/search/{session_id}").status_code == 404
        assert stranger_client.get(
            f"/api/recommendations/session/{session_id}"
        ).status_code == 404

    assert len(cookie) == 43


def test_legacy_unowned_sessions_are_preserved_but_hidden_from_guest_history():
    with SessionLocal() as db:
        legacy = SearchSession(raw_query="Legacy unowned history")
        db.add(legacy)
        db.commit()
        session_id = legacy.id

    with TestClient(app) as guest_client:
        history = guest_client.get("/api/history")
        assert history.status_code == 200
        assert all(item["session_id"] != session_id for item in history.json()["items"])
        assert guest_client.get(f"/api/history/{session_id}").status_code == 404

    with SessionLocal() as db:
        assert db.get(SearchSession, session_id) is not None


def test_pending_session_without_requirement_has_readable_detail():
    with TestClient(app) as client:
        analyzed = client.post(
            "/api/requirements/analyze",
            json={"raw_query": "Tai nghe cho học online"},
        )
        assert analyzed.status_code == 200, analyzed.text
        owner_session_id = analyzed.json()["session_id"]
        with SessionLocal() as db:
            owner_id = db.get(SearchSession, owner_session_id).user_id
            session = SearchSession(user_id=owner_id, raw_query="Chưa phân tích")
            db.add(session)
            db.commit()
            session_id = session.id

        response = client.get(f"/api/history/{session_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "PENDING"
        assert response.json()["result"] is None


def test_history_detail_uses_snapshot_even_after_offer_changes_and_failed_rerun(monkeypatch):
    with TestClient(app) as client:
        with SessionLocal() as db:
            seed_headphones(db, count=1)
        analyzed = client.post("/api/requirements/analyze", json={"raw_query": "Tai nghe 500 nghìn học online mic tốt"})
        session_id = analyzed.json()["session_id"]
        original = client.post("/api/search", json={"session_id": session_id}).json()
        assert original["recommendations"]
        with SessionLocal() as db:
            for offer in db.scalars(select(ProductOffer)):
                offer.price = 9999999
            db.commit()

        async def fail(*args, **kwargs):
            raise RuntimeError("Provider unavailable")

        monkeypatch.setattr(LiveProductSource, "is_available", lambda self, db: True)
        monkeypatch.setattr(LiveProductSource, "search", fail)
        rerun = client.post("/api/search", json={"session_id": session_id})
        assert rerun.status_code == 200
        response = client.get(f"/api/history/{session_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["result"]["data_semantics"] == "snapshot"
        assert body["result"]["recommendations"] == rerun.json()["recommendations"]
        assert body["result"]["warnings"]
        assert body["result"] == client.get(f"/api/search/{session_id}").json()
        item = client.get("/api/history").json()["items"][0]
        assert item["recommendation_count"] == len(rerun.json()["recommendations"])
        assert item["status"] == "COMPLETED"
