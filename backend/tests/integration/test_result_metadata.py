"""Result provenance must stay with the snapshot, not current server/catalog data."""

from datetime import datetime, timezone
from copy import deepcopy

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.product_offer import ProductOffer
from app.models.recommendation_snapshot import RecommendationSnapshot


def completed_session(client):
    analyzed = client.post("/api/requirements/analyze", json={"raw_query": "Tai nghe 500 nghìn để học online mic tốt"})
    session_id = analyzed.json()["session_id"]
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    return session_id, response.json()


def test_snapshot_mode_and_offer_time_survive_runtime_changes(monkeypatch):
    with TestClient(app) as client:
        session_id, original = completed_session(client)
        assert original["data_mode"] == "demo"
        assert original["recommendations"][0]["last_checked_at"]
        with SessionLocal() as db:
            for offer in db.scalars(select(ProductOffer)):
                offer.last_checked_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
            db.commit()
        monkeypatch.setattr(get_settings(), "demo_mode", False)
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["demo_mode"] is False  # Runtime config is deliberately distinct.
        assert loaded["data_mode"] == "demo"
        assert loaded["recommendations"] == original["recommendations"]


def test_old_snapshots_do_not_invent_provenance_or_timestamp():
    with TestClient(app) as client:
        session_id, _ = completed_session(client)
        with SessionLocal() as db:
            snapshot = db.get(RecommendationSnapshot, session_id)
            payload = deepcopy(snapshot.payload)
            payload["result"].pop("data_mode")
            for item in payload["result"]["recommendations"]:
                item.pop("last_checked_at")
            snapshot.payload = payload
            db.commit()
        response = client.get(f"/api/search/{session_id}")
        assert response.status_code == 200
        assert response.json()["data_mode"] is None
        assert response.json()["recommendations"][0]["last_checked_at"] is None


def test_live_snapshot_and_cache_hit_keep_mode_when_server_switches_to_demo(monkeypatch):
    from app.services.search import search_service
    from app.services.search.mock_provider import MockSearchProvider
    from app.services.extraction.product_image_resolver import ProductImageResolver

    from tests.fixtures.sales_pages import sales_page
    from app.services.extraction.product_extraction_service import ProductExtractionService
    from app.schemas.search import SearchSourceItem
    from app.services.normalization.price_parser import parse_price
    async def no_network(self, url):
        rows = await MockSearchProvider().search("tai nghe", 5)
        row = next(r for r in rows if r.url == url)
        raw = ProductExtractionService().extract(SearchSourceItem(title=row.title, content=row.content, url=row.url))
        return url, sales_page(name=raw.name, price=parse_price(raw.price_text))

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(search_service, "get_search_provider", MockSearchProvider)
    monkeypatch.setattr(ProductImageResolver, "_fetch_html", no_network)
    with TestClient(app) as client:
        ids = [client.post("/api/requirements/analyze", json={"raw_query": "Tai nghe 500 nghìn học online mic tốt"}).json()["session_id"] for _ in range(2)]
        monkeypatch.setattr(settings, "demo_mode", False)
        first = client.post("/api/search", json={"session_id": ids[0]})
        cached = client.post("/api/search", json={"session_id": ids[1]})
        assert first.status_code == cached.status_code == 200
        assert first.json()["data_mode"] == cached.json()["data_mode"] == "live"
        assert any("cache" in text for text in cached.json()["warnings"])
        monkeypatch.setattr(settings, "demo_mode", True)
        loaded = client.get(f"/api/search/{ids[1]}").json()
        assert loaded["demo_mode"] is True
        assert loaded["data_mode"] == "live"
        assert loaded["recommendations"] == first.json()["recommendations"]
