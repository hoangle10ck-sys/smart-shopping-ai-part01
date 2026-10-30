"""Automatic shopping search never substitutes demo fixtures for real offers."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.mark.parametrize("query,category,budget", [
    ("Tôi có 500 nghìn, cần tai nghe để học online, mic tốt, pin lâu.", "tai nghe", 500000),
    ("Tôi cần laptop khoảng 15 triệu để học lập trình.", "laptop", 15000000),
    ("Tôi có 5 triệu, cần điện thoại để chụp ảnh và chơi game, ưu tiên camera tốt, pin lâu.",
     "điện thoại", 5000000),
])
def test_automatic_search_does_not_return_demo_fixtures(monkeypatch, query, category, budget):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "tavily_api_key", "")
    monkeypatch.setattr(settings, "searxng_base_url", "")

    with TestClient(app) as client:
        analysis = client.post("/api/requirements/analyze", json={"raw_query": query})
        assert analysis.status_code == 200
        analyzed = analysis.json()
        assert not analyzed["needs_clarification"]
        assert analyzed["requirement"]["category"] == category
        assert analyzed["requirement"]["budget_max"] == budget

        result = client.post("/api/search", json={"session_id": analyzed["session_id"]})
        assert result.status_code == 200
        body = result.json()

    assert body["data_mode"] == "unified"
    assert body["recommendations"] == []
    assert body["total_recommended"] == 0
    assert all(item["source"] != "demo_mock" for item in body["unified_sources"])
    web_source = next(item for item in body["unified_sources"]
                      if item["source"] == "configured_web_search")
    assert web_source["available"] is False
