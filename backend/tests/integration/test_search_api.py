"""Integration tests for the search pipeline."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.raw_product_candidate import RawProductCandidate
from app.models.recommendation import Recommendation
from app.models.product import Product
from app.models.product_offer import ProductOffer
from app.models.source import Source
from app.models.search_session import SearchSession, SearchSessionStatus
from app.services.search.base import SearchProviderError
from app.services.search.base import SearchResult
from app.services.search.mock_provider import MockSearchProvider


client = TestClient(app)


def test_unified_search_does_not_return_demo_products(monkeypatch) -> None:
    """Demo mode configuration cannot inject mock products into shopping search."""

    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "demo_mode", True)
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
    assert data["total_results"] == 0
    assert data["total_sources"] >= 0
    assert data["total_products"] == 0
    assert data["raw_products"] == []
    assert all(item["source"] != "demo_mock" for item in data["unified_sources"])


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
    assert data["total_products"] == 0
    assert data["raw_products"] == []


def _analyze_session() -> str:
    response = client.post(
        "/api/requirements/analyze",
        json={"raw_query": "Tôi có 500 nghìn cần tai nghe học online mic tốt pin lâu"},
    )
    assert response.status_code == 200
    assert response.json()["needs_clarification"] is False
    return response.json()["session_id"]


def test_legacy_platforms_scope_remains_an_alias_for_unified_search() -> None:
    session_id = _analyze_session()

    response = client.post(
        "/api/search",
        json={"session_id": session_id, "search_scope": "platforms"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_mode"] == "unified"
    assert all(source["source"] != "demo_mock" for source in body["unified_sources"])


def test_searxng_candidates_are_returned_without_product_or_offer_ingestion(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.models.product import Product
    from app.models.product_offer import ProductOffer
    from sqlalchemy import func, select

    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr(settings, "searxng_base_url", "http://searxng.test")

    async def discover(self, query: str, max_results: int):
        return [SearchResult(
            title="Laptop result",
            url="https://shop.example/products/laptop-x",
            content="Laptop result snippet mentions a price, which is not product evidence.",
        )]

    monkeypatch.setattr("app.services.search.searxng_provider.SearXNGProvider.search", discover)

    with SessionLocal() as db:
        before_products = db.scalar(select(func.count()).select_from(Product))
        before_offers = db.scalar(select(func.count()).select_from(ProductOffer))

    session_id = _analyze_session()
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200, response.text
    body = response.json()

    discovery = next(item for item in body["unified_sources"] if item["source"] == "web_discovery")
    assert discovery["available"] is True, discovery.get("error")
    assert discovery["matched_products"] == discovery["ingested_rows"] == 0
    assert discovery["web_candidates_count"] == 1
    assert discovery["web_candidates"] == [{
        "title": "Laptop result",
        "url": "https://shop.example/products/laptop-x",
        "domain": "shop.example",
        "status": "DISCOVERED",
        "review_status": "REVIEW_REQUIRED",
        "collector_eligible": False,
        "source": "searxng",
    }]
    assert "price" not in discovery["web_candidates"][0]
    assert "content" not in discovery["web_candidates"][0]

    loaded = client.get(f"/api/search/{session_id}")
    assert loaded.status_code == 200
    saved_discovery = next(
        item for item in loaded.json()["unified_sources"] if item["source"] == "web_discovery"
    )
    assert saved_discovery == discovery

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Product)) == before_products
        assert db.scalar(select(func.count()).select_from(ProductOffer)) == before_offers


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

    with SessionLocal() as db:
        source = Source(url="https://fixture.test/catalog", domain="fixture.test", title="Synthetic test catalog")
        product = Product(name="Synthetic test headphones", category="tai nghe", brand="Fixture", model="Offline-1", normalized_name="synthetic test headphones", image_url="https://fixture.test/images/headphones.jpg")
        db.add_all([source, product])
        db.flush()
        db.add(ProductOffer(product_id=product.id, merchant="Synthetic fixture", price=400000, currency="VND", availability="in_stock", source_id=source.id, product_url="https://fixture.test/catalog/headphones"))
        db.commit()

    success = client.post("/api/search", json={"session_id": session_id})
    assert success.status_code == 200
    before = success.json()
    assert before["recommendations"]
    async def fail_live_search(self, **kwargs):
        raise SearchProviderError("provider unavailable", kind="timeout")

    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.is_available", lambda self, db: True)
    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.search", fail_live_search)
    failed = client.post("/api/search", json={"session_id": session_id})
    assert failed.status_code == 200
    with SessionLocal() as db:
        assert db.get(SearchSession, session_id).status == SearchSessionStatus.COMPLETED

    # Separate requests/database sessions must retain both warnings and results.
    with TestClient(app) as reader:
        reader.cookies.update(client.cookies)
        loaded = reader.get(f"/api/search/{session_id}")
        assert loaded.status_code == 200
        body = loaded.json()
        assert body["status"] == "COMPLETED"
        assert body["warnings"]
        assert body["enhancement"]["status"] == "failed"
        assert body["recommendations"]
        live = next(item for item in body["unified_sources"] if item["source"] == "configured_web_search")
        assert live["error"]
        assert body["raw_products"]
        assert reader.get(f"/api/search/{session_id}").json()["warnings"] == body["warnings"]


def test_first_search_failure_is_readable_without_results(monkeypatch) -> None:
    session_id = _analyze_session()
    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.is_available", lambda self, db: True)
    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.search", lambda self, **kwargs: _provider_failure(self, "query", 5))
    failed = client.post("/api/search", json={"session_id": session_id})
    assert failed.status_code == 200
    loaded = client.get(f"/api/search/{session_id}")
    assert loaded.status_code == 200
    assert loaded.json()["status"] == "COMPLETED"
    assert loaded.json()["warnings"]
    assert loaded.json()["recommendations"] == []
    assert loaded.json()["raw_products"] == []
    with SessionLocal() as db:
        session = db.get(SearchSession, session_id)
        assert session.status == SearchSessionStatus.COMPLETED
        assert session.completed_at is not None


def test_successful_retry_clears_failure_warnings(monkeypatch) -> None:
    session_id = _analyze_session()
    with SessionLocal() as db:
        source = Source(url="https://retry-fixture.test/item", domain="retry-fixture.test", title="Synthetic persisted fixture")
        product = Product(name="Synthetic headphones", category="tai nghe", normalized_name="synthetic headphones", image_url="https://retry-fixture.test/images/headphones.jpg")
        db.add_all([source, product])
        db.flush()
        db.add(ProductOffer(product_id=product.id, merchant="Synthetic QA", price=400000, currency="VND", availability="in_stock", source_id=source.id, product_url=source.url))
        db.commit()
    with monkeypatch.context() as failing:
        failing.setattr("app.services.search.unified.orchestrator.LiveProductSource.is_available", lambda self, db: True)
        async def fail_live(self, **kwargs):
            raise SearchProviderError("provider unavailable", kind="timeout")
        failing.setattr("app.services.search.unified.orchestrator.LiveProductSource.search", fail_live)
        assert client.post("/api/search", json={"session_id": session_id}).status_code == 200
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["recommendations"]
    assert response.json()["warnings"]
    loaded = client.get(f"/api/search/{session_id}").json()
    assert loaded["status"] == "COMPLETED"
    assert "provider unavailable" not in str(loaded["warnings"])


@pytest.mark.parametrize("empty_success", [False, True])
def test_partial_search_failure_keeps_success_and_warnings(monkeypatch, empty_success) -> None:
    session_id = _analyze_session()
    with SessionLocal() as db:
        if not empty_success:
            source = Source(url="https://partial-api-fixture.test/item", domain="partial-api-fixture.test", title="Synthetic persisted fixture")
            product = Product(name="Synthetic headphones", category="tai nghe", normalized_name="synthetic headphones", image_url="https://partial-api-fixture.test/images/headphones.jpg")
            db.add_all([source, product])
            db.flush()
            db.add(ProductOffer(product_id=product.id, merchant="Synthetic QA", price=400000, currency="VND", availability="in_stock", source_id=source.id, product_url=source.url))
            db.commit()
    async def fail_live(self, **kwargs):
        raise SearchProviderError("provider unavailable", kind="timeout")
    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.is_available", lambda self, db: True)
    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.search", fail_live)
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["warnings"]
    assert bool(body["recommendations"]) is not empty_success
    loaded = client.get(f"/api/search/{session_id}").json()
    assert loaded["status"] == "COMPLETED"
    assert loaded["warnings"] == body["warnings"]


def test_successful_empty_search_is_not_provider_failure(monkeypatch) -> None:
    session_id = _analyze_session()
    async def empty_search(self, query: str, max_results: int):
        from app.services.search.unified.base import SourceOutcome
        return SourceOutcome(source_name="configured_web_search")

    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.is_available", lambda self, db: True)
    monkeypatch.setattr("app.services.search.unified.orchestrator.LiveProductSource.search", empty_search)
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["recommendations"] == []
    assert response.json()["warnings"]
