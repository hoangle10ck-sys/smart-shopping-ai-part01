"""Offline fixtures only; these are NOT evidence of real dataset ingestion."""
import gzip
import json
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import Product, ProductOffer, ResearchProduct, HistoricalPriceReference, ResearchImportRun
from app.services.research.importer import import_catalog, map_record, historical_amount, safe_image


def record(**changes):
    return dict(title="Fixture phone device", parent_asin="B000000001", price="19.95",
                categories=["Cell Phones & Accessories", "Cell Phones", "Unlocked Cell Phones"],
                details={"Brand": "Fixture", "RAM": "8 GB"}, average_rating=4.5, rating_number=10, **changes)


def write_records(path, records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


@pytest.mark.parametrize("value", [None, "None", "", "USD 20", "₫20000", "NaN", "Infinity", -1, True, "1e3", "12-20", "1.001", 0])
def test_unknown_price(value):
    assert historical_amount(value) is None


def test_currency_and_safe_images():
    assert historical_amount(19.95) == "19.95"
    for url in ["http://127.0.0.1/a", "javascript:alert(1)", "https://evil.test/a", "https://m.media-amazon.com:123/a"]:
        assert safe_image(url) is None
    assert safe_image("https://m.media-amazon.com/images/a.jpg")


@pytest.mark.parametrize("leaf", ["Earbud Headphones", "On-Ear Headphones", "Over-Ear Headphones"])
def test_headphone_leaf_and_accessory_precedence(leaf):
    raw = record()
    raw.update(title="Fixture wireless headphones", categories=["Electronics", "Headphones & Earbuds", leaf])
    assert map_record(raw, "Electronics")["product"]["category"] == "tai nghe"
    raw["title"] = "Replacement cable for headphones"
    assert map_record(raw, "Electronics")["product"]["category"] == "phu kien dien tu"


def test_stratified_import_preserves_original_lines_and_is_idempotent(tmp_path):
    rows = [record() for _ in range(4)]
    for index, row in enumerate(rows):
        row["parent_asin"] = f"B{index:09d}"
    rows[0]["title"] = "Fixture phone case"
    path = write_records(tmp_path / "quota.jsonl", rows)
    with SessionLocal() as db:
        args = dict(path=path, revision="fixture", category="Cell_Phones_and_Accessories", category_quotas={"dien thoai": 2})
        first = import_catalog(db, **args)
        db.commit()
        second = import_catalog(db, **args)
        assert first["imported"] == 2 and first["outside_quota"] == 2
        assert first["selected_categories"] == {"dien thoai": 2}
        assert second["imported"] == 0 and second["duplicates"] == 2
        assert list(db.scalars(select(ResearchProduct.line_number).order_by(ResearchProduct.line_number))) == [2, 3]


def test_mapping_does_not_infer_sku_brand_or_device():
    raw = record()
    assert map_record(raw, "Cell_Phones_and_Accessories")["product"]["category"] == "dien thoai"
    raw.update(title="Phone case for Fixture", details={}, store="Seller-like store")
    mapped = map_record(raw, "Cell_Phones_and_Accessories")
    assert mapped["product"]["category"] == "phu kien dien thoai"
    assert mapped["product"]["brand"] is None
    assert "sku" not in mapped


def test_import_dry_run_idempotency_and_version(tmp_path):
    path = write_records(tmp_path / "fixture.jsonl", [record(), record()])
    with SessionLocal() as db:
        kw = dict(path=path, revision="fixture-v1", category="Cell_Phones_and_Accessories")
        dry = import_catalog(db, **kw, dry_run=True)
        assert dry["imported"] == 1 and dry["duplicates"] == 1
        assert db.scalar(select(func.count(Product.id))) == 0
        first = import_catalog(db, **kw)
        db.commit()
        second = import_catalog(db, **kw)
        db.commit()
        assert first["input_sha256"] == second["input_sha256"]
        assert second["imported"] == 0 and second["duplicates"] == 2
        assert db.scalar(select(func.count(Product.id))) == 1
        assert db.scalar(select(func.count(ProductOffer.id))) == 0
        ref = db.scalar(select(HistoricalPriceReference))
        assert Decimal(ref.amount) == Decimal("19.95") and ref.currency == "USD"
        assert ref.price_observed_at is None and ref.reference_year == 2023
        assert db.scalar(select(ResearchProduct)).record_sha256
        assert db.scalar(select(func.count(ResearchImportRun.id))) == 2
        kw["revision"] = "fixture-v2"
        import_catalog(db, **kw)
        assert db.scalar(select(func.count(Product.id))) == 2


def test_gzip_corrupt_and_identity_conflict(tmp_path):
    path = tmp_path / "fixture.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write("invalid JSON\n" + json.dumps(record()) + "\n" + json.dumps({}) + "\n")
    with SessionLocal() as db:
        kw = dict(path=path, revision="fixture", category="Electronics")
        report = import_catalog(db, **kw)
        assert report["imported"] == 1 and report["skipped"] == 2
        changed = record()
        changed["price"] = 30
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            stream.write(json.dumps(changed) + "\n")
        report = import_catalog(db, **kw)
        assert report["errors"] == {"identity_content_conflict": 1}
        assert db.scalar(select(HistoricalPriceReference)).amount == "19.95"


def test_giant_record_rolls_back(tmp_path):
    path = tmp_path / "huge.jsonl"
    path.write_text(json.dumps(record()) + "\n" + "x" * (1024 * 1024 + 1), encoding="utf-8")
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="limit"):
            import_catalog(db, path=path, revision="fixture", category="Electronics")
        assert db.scalar(select(func.count(Product.id))) == 0


@pytest.mark.parametrize("changes", [{"parent_asin": "not an id"}, {"categories": []}, {"title": "x"}, {"details": "__import__('os')"}])
def test_invalid_schema(changes):
    raw = record()
    raw.update(changes)
    with pytest.raises(ValueError):
        map_record(raw, "Electronics")
