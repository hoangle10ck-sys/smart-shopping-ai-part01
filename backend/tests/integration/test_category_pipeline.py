"""Unified search keeps verified product categories through persistence and filtering."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.product import Product
from app.services.extraction.product_image_resolver import ProductImageResolver
from app.services.llm import requirement_analyzer
from app.services.llm.client import MockLLMClient
from app.services.search.base import SearchResult
from app.services.search.multi_provider import MultiSearchProvider
from app.services.search.unified.external_sources import LiveProductSource


@pytest.mark.parametrize("name, category, expected", [
    ("Sony headphones H20", "tai nghe", "tai nghe"),
    ("StudyBeat M5", "tai nghe", "tai nghe"),
    ("Unknown Device X1", None, None),
    ("Laptop ASUS Vivobook", "laptop", "laptop"),
])
def test_unified_search_uses_verified_product_category(monkeypatch, name, category, expected):
    settings = get_settings()
    for key, value in {
        "demo_mode": False,
        "openai_api_key": "",
        "gemini_api_key": "",
        "tavily_api_key": "",
        "searxng_base_url": "",
        "top_k": 5,
    }.items():
        monkeypatch.setattr(settings, key, value)

    class Provider:
        async def search(self, query, max_results):
            return [SearchResult(
                title=name,
                url="https://category-test.example/product",
                content=f"{name} giá bán 14.000.000 VND mua ngay tại cửa hàng.",
            )]

    async def inspect(self, url, **kwargs):
        proof = {
            "product_page_valid": True,
                "verification_level": "VERIFIED_CONTENT",
            "page_fetched": True,
            "name": name,
            "category": category,
            "price": 14_000_000,
            "currency": "VND",
            "product_url": url,
            "merchant": "Category Test",
            "availability": "in_stock",
            "specifications": {"ram": "16GB"} if category == "laptop" else {},
        }
        if category is not None:
            proof.update(
                image_url="https://category-test.example/images/product.jpg",
                image_source="synthetic_product_record",
                image_probe={
                    "accepted": True,
                    "checked_at": "2026-10-29T19:00:00+00:00",
                    "content_type": "image/jpeg",
                    "content_sha256": "a" * 64,
                },
            )
        return proof

    monkeypatch.setattr(requirement_analyzer, "get_llm_client", MockLLMClient)
    monkeypatch.setattr(MultiSearchProvider, "__init__", lambda self, **kwargs: setattr(self, "providers", [Provider()]))
    monkeypatch.setattr(ProductImageResolver, "inspect", inspect)
    monkeypatch.setattr(LiveProductSource, "is_available", lambda self, db: True)

    with TestClient(app) as client:
        analyzed = client.post("/api/requirements/analyze", json={
            "raw_query": "Laptop 15 triệu để học lập trình, RAM 16GB",
        })
        assert analyzed.status_code == 200
        session_id = analyzed.json()["session_id"]
        result = client.post("/api/search", json={"session_id": session_id})
        assert result.status_code == 200
        body = result.json()
        assert body["status"] == "COMPLETED"
        if expected == "laptop":
            assert len(body["recommendations"]) == 1
            assert body["recommendations"][0]["category"] == "laptop"
        else:
            assert body["recommendations"] == []
        loaded = client.get(f"/api/search/{session_id}").json()
        assert loaded["recommendations"] == body["recommendations"]

    with SessionLocal() as db:
        product = db.scalar(select(Product))
        if product is not None:
            assert product.category == expected
