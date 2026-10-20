"""Offline research API integration; synthetic fixtures clearly separated from R07."""
import json
import socket

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.core.database import SessionLocal
from app.models import Product, ProductOffer, ResearchProduct
from app.services.research.importer import import_catalog
from app.services.research.recommendation import parse_query


def seed(tmp_path):
    rows = [dict(parent_asin=f"B{i:09d}", title=f"Fixture Phone {i}",
                 categories=["Cell Phones & Accessories", "Unlocked Cell Phones"],
                 price=price, details=details, average_rating=4.0, rating_number=12)
            for i, (price, details) in enumerate([(19.95, {"RAM": "8 GB"}), (21, {}), (None, {}), ("19.99", {"RAM": "16 GB"})], 1)]
    path = tmp_path / "fixture.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    with SessionLocal() as db:
        import_catalog(db, path=path, category="Cell_Phones_and_Accessories", revision="fixture")
        db.commit()


def test_parser():
    assert parse_query("phụ kiện điện thoại dưới 50 USD").budget_max == 50
    assert parse_query("điện thoại dưới 10 triệu").budget_max == 10000000
    parsed = parse_query("điện thoại RAM 8GB")
    assert parsed.requirements[0].priority == 5
    assert parse_query("không rõ muốn mua gì").category is None
    assert parse_query("điện thoại tối thiểu 10 USD").budget_min == 10


def test_fractional_budget_is_not_silently_changed():
    response = TestClient(app).post("/api/research/search", json={"raw_query": "điện thoại dưới 19.95 USD"})
    assert response.status_code == 422


def test_research_e2e_snapshot_comparison_history(tmp_path, monkeypatch):
    seed(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("Research must not open a network connection")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    client = TestClient(app)
    response = client.post("/api/research/search", json={"raw_query": "điện thoại dưới 20 USD"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["data_mode"] == "research" and result["total_recommended"] == 2
    items = result["recommendations"]
    assert all(r["price"] is None and r["offer_quality"] is None and r["offer_id"] is None for r in items)
    assert items[0]["historical_price"]["currency"] == "USD"
    assert items[0]["source_mode"] == "HISTORICAL_RESEARCH"
    sid = result["session_id"]
    comparison = client.post("/api/comparisons", json={"session_id": sid, "product_ids": [r["product_id"] for r in items]})
    assert comparison.status_code == 201, comparison.text
    compared = comparison.json()["result"]["products"]
    assert compared[0]["historical_price"] and compared[0]["best_offer"] is None
    with SessionLocal() as db:
        db.get(Product, items[0]["product_id"]).name = "Changed catalog name"
        db.commit()
        assert db.scalar(select(func.count(ProductOffer.id))) == 0
    saved = client.get(f"/api/search/{sid}").json()
    assert saved["demo_mode"] is False
    assert saved["recommendations"] == items
    assert client.get(f"/api/history/{sid}").json()["result"]["data_mode"] == "research"
    detail = client.get(f"/api/products/{items[0]['product_id']}?session_id={sid}").json()
    assert detail["source_mode"] == "HISTORICAL_RESEARCH"
    assert detail["offers"] == [] and detail["recommendation"] == items[0]
    assert client.post("/api/search", json={"session_id": sid}).status_code == 409


def test_unknown_exact_and_incompatible_budget(tmp_path):
    seed(tmp_path)
    client = TestClient(app)
    result = client.post("/api/research/search", json={"raw_query": "điện thoại RAM 8GB"}).json()
    assert result["total_recommended"] == 1
    assert result["recommendations"][0]["requirement_matches"][0]["status"] == "matched"
    unknown = client.post("/api/research/search", json={"raw_query": "điện thoại RAM 999GB"}).json()
    assert unknown["total_recommended"] == 0
    vnd = client.post("/api/research/search", json={"raw_query": "điện thoại dưới 1 VND"}).json()
    assert vnd["total_recommended"] == 4
    assert any("BUDGET_NOT_COMPARABLE" in w for w in vnd["warnings"])
    assert all(r["product_suitability"]["breakdown"]["budget"] is None for r in vnd["recommendations"])


def test_live_dedup_cannot_modify_historical_identity(tmp_path):
    from app.services.dedup.product_deduplicator import ProductDeduplicator
    from app.schemas.normalization import NormalizedProductCandidate
    seed(tmp_path)
    with SessionLocal() as db:
        product = db.scalar(select(Product).join(ResearchProduct, Product.id == ResearchProduct.product_id))
        candidate = NormalizedProductCandidate(name=product.name, normalized_name=product.normalized_name, category=product.category)
        assert ProductDeduplicator().find_match(db, candidate) is None
