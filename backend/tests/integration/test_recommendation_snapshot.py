"""Session views must not mix historical scoring with mutable product offers."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.product_offer import ProductOffer
from app.models.recommendation import Recommendation
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.services.search.base import SearchResult
from app.services.search.mock_provider import MockSearchProvider


@pytest.fixture
def provider(monkeypatch):
    state = {"price": 15000000, "fail": False}

    async def search(self, query, max_results):
        if state["fail"]:
            raise RuntimeError("Provider unavailable")
        return [SearchResult(
            title="Laptop Snapshot X1",
            url="https://snapshot.example/laptop",
            content=(f"PRODUCT: Laptop Snapshot X1 | PRICE: {state['price']} VND | "
                     "RATING: 4.5/5 | REVIEWS: 120 | SPECS: ram=16GB; storage=512GB"),
        )]

    monkeypatch.setattr(MockSearchProvider, "search", search)
    return state


def search_session(client, budget=15000000):
    response = client.post("/api/requirements/analyze", json={
        "raw_query": f"Laptop {budget} VND để học lập trình, RAM 16GB",
    })
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    return session_id, response.json()


def assert_counts(body):
    assert body["total_found"] == len(body["candidates"]) == len(body["filter_decisions"])
    assert body["total_filtered"] == sum(d["accepted"] for d in body["filter_decisions"])
    assert body["total_recommended"] == len(body["recommendations"])
    assert 0 <= body["total_recommended"] <= body["total_filtered"] <= body["total_found"]


def test_session_a_preserves_price_score_evidence_after_session_b(provider):
    with TestClient(app) as client:
        session_a, original = search_session(client)
        assert original["recommendations"][0]["price"] == 15000000
        assert original["recommendations"][0]["requirement_matches"][0]["status"] == "matched"
        assert next(field["value"] for field in original["recommendations"][0]["evidence"]["fields"]
                    if field["field"] == "price") == 15000000
        with SessionLocal() as db:
            recommendation_id = db.scalar(select(Recommendation.id).where(Recommendation.session_id == session_a))

        provider["price"] = 20000000
        _, newer = search_session(client, budget=25000000)
        assert newer["recommendations"][0]["price"] == 20000000
        with SessionLocal() as db:
            assert db.scalar(select(ProductOffer.price)) == 20000000

        loaded = client.get(f"/api/search/{session_a}")
        assert loaded.status_code == 200
        body = loaded.json()
        assert body["data_semantics"] == "snapshot"
        for field in ("requirement", "candidates", "filter_decisions", "recommendations",
                      "total_found", "total_filtered", "total_recommended"):
            assert body[field] == original[field]
        assert_counts(body)
        assert client.get(f"/api/recommendations/session/{session_a}").json()["items"] == original["recommendations"]
        detail = client.get(f"/api/recommendations/{recommendation_id}").json()
        assert detail["item"] == original["recommendations"][0]


def test_failed_rerun_preserves_snapshot_and_phase1_warnings(provider):
    with TestClient(app) as client:
        session_id, original = search_session(client)
        provider["fail"] = True
        assert client.post("/api/search", json={"session_id": session_id}).status_code == 503
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["recommendations"] == original["recommendations"]
        assert loaded["status"] == "FAILED"
        assert loaded["warnings"]
        assert loaded["data_semantics"] == "snapshot"
        assert_counts(loaded)


def test_successful_rerun_replaces_snapshot_including_empty_results(provider):
    with TestClient(app) as client:
        session_id, _ = search_session(client)
        provider["price"] = 20000000
        rerun = client.post("/api/search", json={"session_id": session_id})
        assert rerun.status_code == 200
        assert rerun.json()["recommendations"] == []
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["recommendations"] == []
        assert loaded["candidates"][0]["price"] == 20000000
        assert loaded["data_semantics"] == "snapshot"
        assert_counts(loaded)


def test_top_k_does_not_change_total_filtered(monkeypatch):
    monkeypatch.setattr(get_settings(), "top_k", 1)
    with TestClient(app) as client:
        analyzed = client.post("/api/requirements/analyze", json={
            "raw_query": "Tai nghe 500 nghìn để học online, mic tốt, pin lâu",
        })
        session_id = analyzed.json()["session_id"]
        response = client.post("/api/search", json={"session_id": session_id})
        assert response.status_code == 200
        monkeypatch.setattr(get_settings(), "top_k", 5)
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["total_found"] == 3
        assert loaded["total_filtered"] == 3
        assert loaded["total_recommended"] == 1
        assert_counts(loaded)


def test_legacy_session_recomputes_consistently_without_database_writes(provider):
    with TestClient(app) as client:
        session_id, original = search_session(client, budget=25000000)
        with SessionLocal() as db:
            db.delete(db.get(RecommendationSnapshot, session_id))
            db.commit()
            row = db.scalar(select(Recommendation).where(Recommendation.session_id == session_id))
            historical_score = row.final_score
            historical_explanation = row.explanation
        provider["price"] = 20000000
        search_session(client, budget=25000000)
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["data_semantics"] == "legacy_recomputed"
        item = loaded["recommendations"][0]
        assert item["price"] == 20000000
        assert item["score"]["budget_score"] != original["recommendations"][0]["score"]["budget_score"]
        assert "20000000" in str(item["evidence"])
        assert "20000000" in str(item["explanation"])
        assert_counts(loaded)
        with SessionLocal() as db:
            assert db.get(RecommendationSnapshot, session_id) is None
            row = db.scalar(select(Recommendation).where(Recommendation.session_id == session_id))
            assert row.final_score == historical_score
            assert row.explanation == historical_explanation


def test_legacy_empty_result_keeps_filter_totals(provider):
    with TestClient(app) as client:
        session_id, original = search_session(client, budget=10000000)
        assert original["recommendations"] == []
        with SessionLocal() as db:
            db.delete(db.get(RecommendationSnapshot, session_id))
            db.commit()
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["data_semantics"] == "legacy_recomputed"
        assert loaded["total_found"] == 1
        assert loaded["total_filtered"] == 0
        assert_counts(loaded)
