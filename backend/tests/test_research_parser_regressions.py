"""Audit regressions: synthetic constraints, never evidence of live ingestion."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.research.recommendation import parse_query
from tests.test_research_pipeline import seed


@pytest.mark.parametrize("query,low,high", [
    ("điện thoại dưới 100 USD RAM tối thiểu 8GB", None, 100),
    ("điện thoại RAM ít nhất 8GB dưới 100 USD", None, 100),
    ("laptop tối thiểu 200 USD RAM tối đa 16GB", 200, None),
    ("phụ kiện điện thoại từ 20 đến 50 USD", 20, 50),
    ("laptop from 20 USD to 50 USD", 20, 50),
    ("laptop between 20 and 50 USD", 20, 50),
    ("điện thoại từ 2 đến 5 triệu", 2000000, 5000000),
    ("điện thoại từ 2 triệu đến 5000000 VND", 2000000, 5000000),
])
def test_budget_scope(query, low, high):
    parsed = parse_query(query)
    assert (parsed.budget_min, parsed.budget_max) == (low, high)


@pytest.mark.parametrize("query", ["laptop từ 50 đến 20 USD", "laptop từ 20 USD đến 50 VND",
                                  "laptop 20 USD hoặc 50 USD", "laptop dưới 19.95 USD"])
def test_ambiguous_or_unsupported_budget_rejected(query):
    with pytest.raises(ValueError):
        parse_query(query)


@pytest.mark.parametrize("negative", ["không mua", "không chọn", "ngoại trừ", "exclude", "not"])
def test_negative_brand(negative):
    parsed = parse_query(f"điện thoại {negative} Apple, chọn Samsung")
    assert parsed.brands == ["Samsung"]
    assert parsed.excluded_requirements == ["Apple"]


def test_api_preserves_price_range_and_ram_comparator(tmp_path):
    seed(tmp_path)
    client = TestClient(app)
    result = client.post("/api/research/search", json={"raw_query": "điện thoại từ 20 đến 50 USD"}).json()
    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["historical_price"]["amount"] == "21.00"
    result = client.post("/api/research/search", json={"raw_query": "điện thoại dưới 100 USD RAM tối thiểu 8GB"}).json()
    assert len(result["recommendations"]) == 2
    assert all(r["requirement_matches"][0]["status"] == "matched" for r in result["recommendations"])
    exact = client.post("/api/research/search", json={"raw_query": "điện thoại RAM 8GB"}).json()
    assert len(exact["recommendations"]) == 1


def test_purpose_is_retained_and_disclosed(tmp_path):
    seed(tmp_path)
    parsed = parse_query("laptop để học lập trình")
    assert parsed.purpose == ["lập trình"]
    result = TestClient(app).post("/api/research/search", json={"raw_query": "laptop để học lập trình"}).json()
    assert any("PURPOSE_NOT_SCORED" in warning for warning in result["warnings"])


def test_negative_brand_filters_actual_catalog(tmp_path):
    from sqlalchemy import select
    from app.models import Product
    from app.core.database import SessionLocal
    seed(tmp_path)
    with SessionLocal() as db:
        products = list(db.scalars(select(Product).order_by(Product.id)))
        products[0].brand = "Apple"
        products[1].brand = "Samsung"
        db.commit()
        apple_id = products[0].id
    result = TestClient(app).post("/api/research/search", json={"raw_query": "điện thoại không mua Apple"}).json()
    assert result["total_recommended"] == 3
    assert apple_id not in [r["product_id"] for r in result["recommendations"]]
