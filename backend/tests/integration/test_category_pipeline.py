"""Category evidence must survive extraction, persistence, filtering and GET."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.product import Product
from app.services.search.base import SearchResult
from app.services.search.mock_provider import MockSearchProvider


@pytest.mark.parametrize("name, label, expected", [
    ("Sony headphones H20", "", "tai nghe"),
    ("StudyBeat M5", "CATEGORY: tai nghe | ", "tai nghe"),
    ("Unknown Device X1", "", None),
    ("Laptop ASUS Vivobook", "", "laptop"),
])
def test_laptop_request_uses_product_category(monkeypatch, name, label, expected):
    async def search(self, query, max_results):
        return [SearchResult(
            title=name,
            url="https://category-test.example/product",
            content=f"PRODUCT: {name} | {label}PRICE: 449000 VND | SPECS: ram=8GB",
        )]

    monkeypatch.setattr(MockSearchProvider, "search", search)
    with TestClient(app) as client:
        analyzed = client.post("/api/requirements/analyze", json={
            "raw_query": "Laptop 15 triệu để học lập trình, RAM 16GB",
        })
        assert analyzed.status_code == 200
        session_id = analyzed.json()["session_id"]
        result = client.post("/api/search", json={"session_id": session_id})
        assert result.status_code == 200
        for body in (result.json(), client.get(f"/api/search/{session_id}").json()):
            assert body["status"] == "COMPLETED"
            assert len(body["candidates"]) == 1
            assert body["candidates"][0]["category"] == expected
            if expected != "laptop":
                assert body["recommendations"] == []
                assert body["filter_decisions"][0]["rejection_stage"] == "category"
            else:
                assert len(body["recommendations"]) == 1
                assert body["recommendations"][0]["score"]["requirement_score"] == 0
        with SessionLocal() as db:
            product = db.scalar(select(Product))
            assert product.category == expected
