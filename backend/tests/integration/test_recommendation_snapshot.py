"""Session views must not mix historical scoring with mutable product offers."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.product_offer import ProductOffer
from app.models.recommendation import Recommendation
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.product import Product
from app.models.source import Source
from app.models.raw_product_candidate import RawProductCandidate
from app.models.requirement import Requirement
from app.models.search_query import SearchQuery
from app.models.search_session import SearchSession, SearchSessionStatus
from app.schemas.recommendation import RecommendationItem
from app.schemas.ranking import ScoreBreakdown
from app.schemas.requirement import RequirementData
from app.services.recommendation.recommendation_service import RecommendationRunResult
from pydantic import TypeAdapter


def search_session(client, budget=15000000, product_count=1):
    response = client.post("/api/requirements/analyze", json={
        "raw_query": f"Laptop {budget} VND để học lập trình, RAM 16GB",
    })
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    return session_id, response.json()


@pytest.fixture
def provider(monkeypatch):
    state = {"price": 15000000, "fail": False}
    from app.models.product import Product

    search_catalog = __import__(
        "app.services.search.unified.catalog_source", fromlist=["DatabaseCatalogSource"]
    ).DatabaseCatalogSource.search

    def seed_catalog(self, *, db, session_id, requirement):
        count = state.get("product_count", 1)
        for index in range(count):
            model = f"X{index + 1}"
            product = db.scalar(select(Product).where(Product.model == model))
            if product is None:
                source = Source(
                    url=f"https://snapshot-shop.test/laptop/{model.lower()}",
                    domain="snapshot-shop.test",
                    title="Synthetic snapshot test fixture",
                    reliability_score=80,
                )
                db.add(source)
                db.flush()
                product = Product(
                    name=f"Laptop Snapshot {model}", category="laptop", brand="Snapshot",
                    model=model, rating=4.5, review_count=120,
                    image_url=f"https://snapshot-shop.test/images/{model.lower()}.jpg",
                    specifications={"ram": "16GB", "storage": "512GB"},
                )
                db.add(product)
                db.flush()
                db.add(ProductOffer(
                    product_id=product.id, merchant="Snapshot Shop", price=state["price"],
                    currency="VND", availability="in_stock", source_id=source.id,
                    product_url=source.url, last_checked_at=datetime.now(timezone.utc),
                ))
            else:
                product.offers[0].price = state["price"]
                product.offers[0].last_checked_at = datetime.now(timezone.utc)

        # A repeated search receives the new observation in its own working
        # rows; the prior session's saved recommendation remains immutable.
        for raw in db.scalars(select(RawProductCandidate).where(RawProductCandidate.session_id == session_id)):
            payload = dict(raw.payload)
            payload["price_text"] = str(state["price"])
            if payload.get("page_validation"):
                payload["page_validation"] = {**payload["page_validation"], "price": state["price"]}
            raw.payload = payload
        db.flush()
        return search_catalog(self, db=db, session_id=session_id, requirement=requirement)

    monkeypatch.setattr(
        "app.services.search.unified.catalog_source.DatabaseCatalogSource.search",
        seed_catalog,
    )

    from app.services.search.unified.base import SourceOutcome

    async def live_search(self, **kwargs):
        if state["fail"]:
            return SourceOutcome(
                source_name=self.name,
                error="RuntimeError",
                warnings=["Configured source failed in the test fixture."],
            )
        return SourceOutcome(source_name=self.name)

    monkeypatch.setattr(
        "app.services.search.unified.orchestrator.LiveProductSource.is_available",
        lambda self, db: True,
    )
    monkeypatch.setattr(
        "app.services.search.unified.orchestrator.LiveProductSource.search",
        live_search,
    )
    return state


def test_unified_search_without_real_products_returns_empty_not_demo():
    with TestClient(app) as client:
        response = client.post("/api/requirements/analyze", json={
            "raw_query": "Tai nghe dưới 500 nghìn để học online",
        })
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        result = client.post("/api/search", json={"session_id": session_id})
        assert result.status_code == 200
        body = result.json()
        assert body["recommendations"] == []
        assert body["total_recommended"] == 0
        assert all(item["source"] != "demo_mock" for item in body["unified_sources"])
        loaded = client.get(f"/api/search/{session_id}")
        assert loaded.status_code == 200
        assert loaded.json()["recommendations"] == []


def assert_counts(body):
    assert body["total_found"] == len(body["candidates"]) == len(body["filter_decisions"])
    assert body["total_filtered"] == sum(d["accepted"] for d in body["filter_decisions"])
    assert body["total_recommended"] == len(body["recommendations"])
    assert 0 <= body["total_recommended"] <= body["total_filtered"] <= body["total_found"]


def seed_snapshot(db):
    session = SearchSession(raw_query="Laptop dưới 25 triệu", status=SearchSessionStatus.COMPLETED)
    db.add(session)
    db.flush()
    requirement = Requirement(session_id=session.id, category="laptop", budget_max=25000000,
        currency="VND", purpose=[], requirements=[], excluded_requirements=[], brands=[], confidence=1.0)
    db.add(requirement)
    db.flush()
    product_id = 1
    item = RecommendationItem(product_id=product_id, rank=1, name="Laptop Snapshot X1", category="laptop",
        brand="Snapshot", model="X1", price=15000000, merchant="Snapshot Shop",
        product_url="https://snapshot-shop.test/laptop", evidence_url="https://snapshot-shop.test/laptop",
        requirement_matches=[{"name":"category","status":"matched","requested_value":"laptop",
                              "product_value":"laptop","reason":"category matches"}],
        evidence={"fields":[{"field":"price","value":15000000}],"confidence":80,
                  "breakdown":{"source_reliability":80,"product_completeness":80,"offer_completeness":80,
                               "consistency":80,"corroboration":80},"source_count":1,"offer_count":1},
        score=ScoreBreakdown(budget_score=80, requirement_score=80, purpose_score=80,
            rating_score=80, review_score=80, source_score=80, final_score=80))
    result = RecommendationRunResult(requirement=RequirementData.model_validate({
        "category":"laptop", "budget_max":25000000, "currency":"VND", "purpose":[],
        "requirements":[], "excluded_requirements":[], "brands":[], "confidence":1.0}),
        candidates=[], filter_decisions=[], recommendations=[item], total_found=1, total_filtered=1,
        data_mode="unified")
    db.add(RecommendationSnapshot(session_id=session.id, payload={"version":1,"result":
        TypeAdapter(RecommendationRunResult).dump_python(result,mode="json")}))
    db.commit()
    return session.id


@pytest.fixture(autouse=True)
def disable_demo_source(monkeypatch):
    """Snapshot API tests use persisted synthetic catalog evidence, never Demo offers."""
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "demo_mode", False)


def test_session_a_preserves_price_score_evidence_after_session_b(provider):
    with TestClient(app) as client:
        session_a, original = search_session(client)
        recommendation_id = original["recommendations"][0]["product_id"]
        assert original["recommendations"][0]["price"] == 15000000
        provider["price"] = 20000000
        _, newer = search_session(client, budget=25000000)
        assert newer["recommendations"][0]["price"] == 20000000
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


def test_failed_live_source_keeps_catalog_results_and_snapshot(provider):
    with TestClient(app) as client:
        session_id, original = search_session(client)
        provider["fail"] = True
        rerun = client.post("/api/search", json={"session_id": session_id})
        assert rerun.status_code == 200
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["recommendations"][0]["price"] == original["recommendations"][0]["price"]
        assert loaded["status"] == "COMPLETED"
        assert loaded["warnings"]
        assert loaded["data_semantics"] == "snapshot"
        assert_counts(loaded)


def test_successful_rerun_replaces_snapshot_including_empty_results(provider):
    with TestClient(app) as client:
        session_id, _ = search_session(client, budget=10000000)
        provider["price"] = 20000000
        rerun = client.post("/api/search", json={"session_id": session_id})
        assert rerun.status_code == 200
        assert rerun.json()["recommendations"] == []
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["recommendations"] == []
        assert loaded["candidates"][0]["price"] == 20000000
        assert loaded["data_semantics"] == "snapshot"
        assert_counts(loaded)


def test_top_k_does_not_change_total_filtered(monkeypatch, provider):
    provider["product_count"] = 3
    monkeypatch.setattr(get_settings(), "top_k", 1)
    with TestClient(app) as client:
        session_id, response_body = search_session(client, budget=25000000, product_count=3)
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
            legacy_product_id = db.scalar(select(Recommendation.product_id).where(Recommendation.session_id == session_id))
            db.delete(db.get(RecommendationSnapshot, session_id))
            db.commit()
            row = db.scalar(select(Recommendation).where(Recommendation.session_id == session_id))
            historical_score = row.final_score if row else None
            historical_explanation = row.explanation if row else None
            price = 20000000
            old_raw = db.scalar(select(RawProductCandidate).where(RawProductCandidate.session_id == session_id))
            assert old_raw is not None
            old_offer = db.scalar(select(ProductOffer).where(ProductOffer.product_id == old_raw.payload.get("product_id")))
            if old_offer is None:
                old_offer = db.scalar(select(ProductOffer).limit(1))
            if old_offer is None:
                source = Source(
                    url=f"https://legacy-{session_id}.test/laptop",
                    domain=f"legacy-{session_id}.test",
                    title="Synthetic legacy fixture",
                    reliability_score=80,
                )
                db.add(source)
                db.flush()
                old_offer = ProductOffer(
                    product_id=legacy_product_id,
                    merchant="Synthetic fixture catalog",
                    price=price,
                    currency="VND",
                    availability="in_stock",
                    source_id=source.id,
                    product_url=source.url,
                    last_checked_at=datetime.now(timezone.utc),
                )
                db.add(old_offer)
            assert old_offer is not None
            old_offer.price = price
            old_offer.last_checked_at = datetime.now(timezone.utc)
            old_raw.payload = {
                **old_raw.payload,
                "price_text": str(price),
                "page_validation": {
                    **old_raw.payload["page_validation"],
                    "price": price,
                    "last_checked_at": old_offer.last_checked_at.isoformat(),
                },
            }
            db.commit()
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
            assert (row.final_score if row else None) == historical_score
            assert (row.explanation if row else None) == historical_explanation


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
