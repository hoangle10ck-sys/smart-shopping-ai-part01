"""Search API cache integration with fake providers and a temporary database."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.product_offer import ProductOffer
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.requirement import Requirement
from app.models.search_cache import SearchCacheEntry
from app.models.search_query import SearchQuery
from app.models.search_session import SearchSession
from app.services.cache.search_cache import DatabaseSearchCache, as_utc
from app.services.extraction.product_image_resolver import ProductImageResolver
from app.services.search import search_service
from app.services.search.base import SearchResult


@pytest.fixture
def live(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "cache_ttl_seconds", 123)
    state = {"price": 15000000, "calls": 0, "fail": False, "during_search": None}

    class Provider:
        async def search(self, query, max_results):
            state["calls"] += 1
            if state["during_search"]:
                state["during_search"]()
            if state["fail"]:
                raise RuntimeError("Mock search failure")
            return [SearchResult(
                title="Laptop Cache X1", url="https://cache-test.example/products/laptop-cache-x1",
                content=f"PRODUCT: Laptop Cache X1 | PRICE: {state['price']} VND | SPECS: ram=16GB",
            )]

    from tests.fixtures.sales_pages import sales_page
    async def page(self, url):
        return url, sales_page(name="Laptop Cache X1", price=state["price"],
                               additionalProperty=[{"name": "ram", "value": "16GB"}])
    monkeypatch.setattr(search_service, "get_search_provider", Provider)
    monkeypatch.setattr(ProductImageResolver, "_fetch_html", page)
    return state


def new_session(budget=25000000):
    with SessionLocal() as db:
        session = SearchSession(raw_query=f"Laptop {budget} VND")
        db.add(session)
        db.flush()
        db.add(Requirement(session_id=session.id, category="laptop", budget_max=budget,
                           purpose=["học lập trình"], requirements=[{"name": "ram", "value": "16GB", "priority": 5}]))
        db.add(SearchQuery(session_id=session.id, query="laptop 16GB", position=1))
        db.commit()
        return session.id


def execute(client, session_id):
    return client.post("/api/search", json={"session_id": session_id})


def test_cache_miss_then_hit_preserves_snapshot_and_ttl(live):
    with TestClient(app) as client:
        a = new_session()
        first = execute(client, a)
        assert first.status_code == 200
        assert live["calls"] == 1
        with SessionLocal() as db:
            entry = db.scalar(select(SearchCacheEntry))
            assert (as_utc(entry.expires_at) - as_utc(entry.created_at)).total_seconds() == 123
            original_expiry = entry.expires_at
        b = new_session()
        live["fail"] = True  # A valid hit must not call the unavailable provider.
        hit = execute(client, b)
        assert hit.status_code == 200
        body = hit.json()
        assert body["recommendations"][0]["requirement_matches"]
        assert body["recommendations"][0]["evidence"]["fields"]
        assert body["session_id"] == b
        assert body["recommendations"] == first.json()["recommendations"]
        assert body["data_semantics"] == "snapshot"
        assert body["status"] == "COMPLETED"
        assert any("cache" in warning for warning in body["warnings"])
        assert live["calls"] == 1
        loaded = client.get(f"/api/search/{b}").json()
        assert loaded["recommendations"] == body["recommendations"]
        assert loaded["warnings"] == body["warnings"]
        with SessionLocal() as db:
            assert db.scalar(select(SearchCacheEntry)).expires_at == original_expiry
        assert client.get(f"/api/history/{b}").json()["result"]["recommendations"] == body["recommendations"]


def test_expired_cache_runs_provider_again(live):
    with TestClient(app) as client:
        execute(client, new_session())
        with SessionLocal() as db:
            db.scalar(select(SearchCacheEntry)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        live["price"] = 20000000
        response = execute(client, new_session())
        assert response.status_code == 200
        assert response.json()["recommendations"][0]["price"] == 20000000
        assert live["calls"] == 2


def test_cache_hit_never_rewrites_newer_shared_offer(live):
    with TestClient(app) as client:
        a = new_session(budget=15000000)
        original = execute(client, a).json()
        live["price"] = 20000000
        assert execute(client, new_session(budget=25000000)).status_code == 200
        c = new_session(budget=15000000)
        cached = execute(client, c)
        assert cached.status_code == 200
        assert cached.json()["recommendations"] == original["recommendations"]
        assert live["calls"] == 2
        with SessionLocal() as db:
            assert db.scalar(select(ProductOffer.price)) == 20000000
        assert client.get(f"/api/search/{a}").json()["recommendations"] == original["recommendations"]


def test_provider_failure_can_use_cache_published_during_request(live):
    with TestClient(app) as client:
        source = new_session()
        original = execute(client, source).json()
        with SessionLocal() as db:
            entry = db.scalar(select(SearchCacheEntry))
            key = entry.key
            db.delete(entry)  # Simulate eviction before another worker repopulates it.
            db.commit()

        def repopulate():
            with SessionLocal() as db:
                DatabaseSearchCache().put(db, key, db.get(RecommendationSnapshot, source), 123)
                db.commit()

        live["during_search"] = repopulate
        live["fail"] = True
        target = new_session()
        response = execute(client, target)
        assert response.status_code == 200
        body = response.json()
        assert body["recommendations"] == original["recommendations"]
        assert any("gặp lỗi" in text for text in body["warnings"])
        assert any("Mock search failure" in text for text in body["warnings"])
        assert client.get(f"/api/search/{target}").json()["warnings"] == body["warnings"]


@pytest.mark.parametrize("expired", [False, True])
def test_provider_failure_without_valid_cache_remains_failed(live, expired):
    with TestClient(app) as client:
        if expired:
            execute(client, new_session())
            with SessionLocal() as db:
                db.scalar(select(SearchCacheEntry)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.commit()
        live["fail"] = True
        target = new_session()
        assert execute(client, target).status_code == 503
        body = client.get(f"/api/search/{target}").json()
        assert body["status"] == "FAILED"
        assert body["warnings"]
        assert body["recommendations"] == []


def test_failed_refresh_keeps_own_snapshot_even_if_other_cache_is_valid(live):
    with TestClient(app) as client:
        a = new_session()
        original = execute(client, a).json()
        with SessionLocal() as db:
            db.scalar(select(SearchCacheEntry)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        live["price"] = 20000000
        b = new_session()
        assert execute(client, b).json()["recommendations"][0]["price"] == 20000000
        live["fail"] = True
        assert execute(client, a).status_code == 503
        loaded = client.get(f"/api/search/{a}").json()
        assert loaded["recommendations"] == original["recommendations"]
        assert loaded["status"] == "FAILED"
        assert loaded["warnings"]


def test_demo_mode_bypasses_live_cache_and_remains_local(live, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    with TestClient(app) as client:
        for _ in range(2):
            response = execute(client, new_session())
            assert response.status_code == 200
            assert response.json()["demo_mode"] is True
            assert response.json()["recommendations"][0]["explanation"]["generation_mode"] == "demo"
        assert live["calls"] == 2
        with SessionLocal() as db:
            assert db.scalar(select(func.count(SearchCacheEntry.key))) == 0
