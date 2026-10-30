"""Unified search rechecks configured sources for each search session."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.search_cache import SearchCacheEntry
from app.models.search_query import SearchQuery
from app.models.search_session import SearchSession
from app.models.requirement import Requirement
from app.services.search.base import SearchResult
from app.services.search.multi_provider import MultiSearchProvider
from app.services.search.unified.external_sources import LiveProductSource
from tests.fixtures.unified_catalog import seed_headphones


def make_session(owner_id: str) -> str:
    with SessionLocal() as db:
        session = SearchSession(user_id=owner_id, raw_query="Tai nghe 500000 VND")
        db.add(session)
        db.flush()
        db.add(Requirement(session_id=session.id, category="tai nghe", budget_max=500000))
        db.add(SearchQuery(session_id=session.id, query="tai nghe", position=1))
        db.commit()
        return session.id


def test_every_unified_search_rechecks_configured_provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    calls: list[str] = []

    class Provider:
        async def search(self, query, max_results):
            calls.append(query)
            return [SearchResult(title="No verified offer", url="https://shop.example/", content="")]

    monkeypatch.setattr(MultiSearchProvider, "__init__", lambda self, **kwargs: setattr(self, "providers", [Provider()]))
    monkeypatch.setattr(LiveProductSource, "is_available", lambda self, db: True)
    with SessionLocal() as db:
        seed_headphones(db, count=1)

    with TestClient(app) as client:
        owner_session = client.post(
            "/api/requirements/analyze",
            json={"raw_query": "Tai nghe 500000 VND học online"},
        )
        assert owner_session.status_code == 200
        with SessionLocal() as db:
            owner_id = db.get(SearchSession, owner_session.json()["session_id"]).user_id

        first = client.post("/api/search", json={"session_id": make_session(owner_id)})
        assert first.status_code == 200
        calls_after_first = len(calls)
        assert calls_after_first > 0

        second = client.post("/api/search", json={"session_id": make_session(owner_id)})
        assert second.status_code == 200
        assert len(calls) > calls_after_first
        assert first.json()["data_mode"] == second.json()["data_mode"] == "unified"
        assert first.json()["status"] == second.json()["status"] == "COMPLETED"

    with SessionLocal() as db:
        assert db.scalar(select(func.count(SearchCacheEntry.key))) == 0
