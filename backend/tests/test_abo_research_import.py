import csv
import gzip
import json
from collections import Counter

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import (
    HistoricalPriceReference,
    Product,
    ProductOffer,
    ResearchImportRun,
    ResearchProduct,
)
from app.services.research.abo_importer import import_catalog, map_record
from app.services.normalization.product_normalizer import infer_product_category
from scripts.download_abo_research_extension import category_for, select_record
from app.services.research.importer import import_catalog as import_amazon_catalog
from app.services.research.recommendation import evaluate, parse_query, provenance
from app.schemas.requirement import RequirementData


def abo_record(item_id="B012345678", product_type="NOTEBOOK_COMPUTER"):
    return {
        "item_id": item_id,
        "domain_name": "amazon.com",
        "item_name": [
            {"language_tag": "de_DE", "value": "Tragbarer Computer"},
            {"language_tag": "en_US", "value": "Example notebook computer"},
        ],
        "brand": [{"language_tag": "en_US", "value": "Example Brand"}],
        "model_name": [{"language_tag": "en_US", "value": "Example Model"}],
        "model_number": [{"value": "MODEL-01"}],
        "model_year": [{"value": "2021"}],
        "product_type": [{"value": product_type}],
        "color": [{"language_tag": "en_US", "value": "Black"}],
        "material": [{"language_tag": "en_US", "value": "Aluminum"}],
        "item_dimensions": {
            "height": {"value": 1.2, "unit": "inches"},
            "width": {"value": 12, "unit": "inches"},
        },
        "item_weight": [{"value": 2.4, "unit": "pounds"}],
        "bullet_point": [{"language_tag": "en_US", "value": "Documented source feature"}],
        "main_image_id": "image123",
        "other_image_id": ["image456"],
    }


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def write_images(path):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["image_id", "height", "width", "path"])
        writer.writeheader()
        writer.writerow({"image_id": "image123", "height": 256, "width": 256, "path": "ab/12345678.jpg"})
        writer.writerow({"image_id": "image456", "height": 256, "width": 256, "path": "cd/87654321.jpg"})
    return path


def test_abo_mapping_uses_source_metadata_and_only_safe_image_paths():
    raw = abo_record()
    mapped = map_record(raw, {"image123": "ab/12345678.jpg"})

    assert mapped["external_product_id"] == "B012345678"
    assert mapped["product"]["name"] == "Example notebook computer"
    assert mapped["product"]["category"] == "laptop"
    assert mapped["product"]["brand"] == "Example Brand"
    assert mapped["product"]["model"] == "Example Model"
    assert mapped["product"]["image_url"] == (
        "https://amazon-berkeley-objects.s3.amazonaws.com/images/small/ab/12345678.jpg"
    )
    assert mapped["product"]["rating"] is None
    assert mapped["product"]["review_count"] is None
    assert mapped["historical_price"] is None
    assert mapped["product"]["specifications"]["model_number"] == "MODEL-01"
    assert "1.2 inches" in mapped["product"]["specifications"]["dimensions"]
    assert "Documented source feature" in mapped["product"]["specifications"]["highlights"]
    assert mapped["metadata"]["license"] == "CC BY 4.0"

    raw["main_image_id"] = "../../attacker"
    assert map_record(raw, {"../../attacker": "../../evil.jpg"})["product"]["image_url"] is None


@pytest.mark.parametrize(
    ("raw", "image_paths"),
    [
        ({}, {}),
        (abo_record(item_id="bad"), {"image123": "ab/12345678.jpg"}),
        (abo_record(product_type="UNKNOWN_TYPE"), {"image123": "ab/12345678.jpg"}),
    ],
)
def test_abo_mapping_rejects_records_without_supported_identity_or_category(raw, image_paths):
    with pytest.raises(ValueError):
        map_record(raw, image_paths)


@pytest.mark.parametrize(
    ("product_type", "category"),
    [
        ("SHOES", "giày"),
        ("GROCERY", "thực phẩm"),
        ("HOME", "đồ gia dụng"),
        ("PET_SUPPLIES", "thú cưng"),
        ("SPORTING_GOODS", "đồ thể thao"),
        ("TELEVISION", "tivi"),
        ("REFRIGERATOR", "tủ lạnh"),
    ],
)
def test_abo_maps_explicit_source_product_types(product_type, category):
    assert map_record(abo_record(product_type=product_type), {})["product"]["category"] == category


@pytest.mark.parametrize(
    ("query", "category"),
    [
        ("giày chạy bộ", "giày"),
        ("thực phẩm", "thực phẩm"),
        ("đồ gia dụng", "đồ gia dụng"),
        ("đồ cho thú cưng", "thú cưng"),
        ("đồ thể thao", "đồ thể thao"),
        ("smart TV", "tivi"),
        ("tủ lạnh", "tủ lạnh"),
    ],
)
def test_research_query_parser_recognizes_expanded_product_categories(query, category):
    assert parse_query(query).category == category


@pytest.mark.parametrize(
    ("source_category", "expected"),
    [
        ("sports equipment", "đồ thể thao"),
        ("grocery", "thực phẩm"),
        ("home appliances", "đồ gia dụng"),
        ("pet supplies", "thú cưng"),
        ("fridge", "tủ lạnh"),
    ],
)
def test_product_normalizer_canonicalizes_expanded_source_categories(source_category, expected):
    assert infer_product_category("Example source listing", source_category) == expected


def test_research_retrieval_returns_products_for_expanded_categories(tmp_path):
    pairs = [
        ("giày chạy bộ", "SHOES", "giày"),
        ("thực phẩm", "GROCERY", "thực phẩm"),
        ("đồ gia dụng", "HOME", "đồ gia dụng"),
        ("đồ cho thú cưng", "PET_SUPPLIES", "thú cưng"),
        ("đồ thể thao", "SPORTING_GOODS", "đồ thể thao"),
        ("smart TV", "TELEVISION", "tivi"),
        ("tủ lạnh", "REFRIGERATOR", "tủ lạnh"),
    ]
    catalog = write_jsonl(
        tmp_path / "abo-categories.jsonl",
        [abo_record(f"B{index:09d}", product_type) for index, (_, product_type, _) in enumerate(pairs, start=1)],
    )
    images = write_images(tmp_path / "images.csv.gz")
    quotas = {category: 1 for _, _, category in pairs}

    with SessionLocal() as db:
        import_catalog(db, path=catalog, image_metadata_path=images, revision="abo-categories-v1",
                       limit=len(pairs), category_quotas=quotas)
        db.commit()
        for query, _product_type, expected_category in pairs:
            parsed = parse_query(query)
            result, _warnings = evaluate(db, parsed)
            assert parsed.category == expected_category
            assert len(result.recommendations) == 1
            assert result.recommendations[0].category == expected_category


def test_abo_extension_selector_excludes_existing_ids_and_enforces_category_quota():
    old = {"B000000001"}
    selected = {}
    counts = Counter()
    shoe = abo_record("B000000002", "SHOES")
    assert category_for(shoe) == "giày"
    assert select_record(shoe, existing_ids=old, selected=selected, counts=counts)
    assert not select_record(shoe, existing_ids=old, selected=selected, counts=counts)
    assert not select_record(abo_record("B000000001", "SHOES"),
                            existing_ids=old, selected=selected, counts=counts)
    for index in range(15):
        assert select_record(abo_record(f"B{index + 10:09d}", "SHOES"),
                            existing_ids=old, selected=selected, counts=counts)
    assert counts["giày"] == 16
    assert not select_record(abo_record("B000000099", "SHOES"),
                             existing_ids=old, selected=selected, counts=counts)


def test_abo_import_is_bounded_idempotent_and_never_creates_price_or_offer(tmp_path):
    catalog = write_jsonl(
        tmp_path / "abo.jsonl",
        [abo_record(), abo_record("B098765432", "HEADPHONES")],
    )
    images = write_images(tmp_path / "images.csv.gz")
    args = dict(
        path=catalog,
        image_metadata_path=images,
        revision="abo-test-v1",
        limit=2,
        category_quotas={"laptop": 1, "tai nghe": 1},
    )

    with SessionLocal() as db:
        dry = import_catalog(db, **args, dry_run=True)
        assert dry["imported"] == 2
        assert db.scalar(select(func.count(Product.id))) == 0

        first = import_catalog(db, **args)
        db.commit()
        second = import_catalog(db, **args)
        db.commit()

        assert first["imported"] == 2
        assert second["imported"] == 0 and second["duplicates"] == 2
        assert db.scalar(select(func.count(Product.id))) == 2
        assert db.scalar(select(func.count(ResearchProduct.id))) == 2
        assert db.scalar(select(func.count(ProductOffer.id))) == 0
        assert db.scalar(select(func.count(HistoricalPriceReference.id))) == 0
        assert db.scalar(select(func.count(ResearchImportRun.id))) == 2
        assert {p.category for p in db.scalars(select(Product))} == {"laptop", "tai nghe"}
        assert {r.dataset_id for r in db.scalars(select(ResearchProduct))} == {"Amazon-Berkeley-Objects"}


def test_default_research_search_keeps_amazon_and_abo_catalogs_visible(tmp_path):
    amazon_row = {
        "title": "Example notebook computer",
        "parent_asin": "B011111111",
        "price": None,
        "categories": ["Electronics", "Laptops"],
        "details": {"Brand": "Example Brand"},
        "images": [],
        "average_rating": None,
        "rating_number": None,
    }
    amazon_path = write_jsonl(tmp_path / "amazon.jsonl", [amazon_row])
    abo_path = write_jsonl(tmp_path / "abo.jsonl", [abo_record("B022222222")])
    images_path = write_images(tmp_path / "images.csv.gz")

    with SessionLocal() as db:
        import_amazon_catalog(
            db,
            path=amazon_path,
            revision="amazon-v1",
            category="Electronics",
            limit=1,
        )
        import_catalog(
            db,
            path=abo_path,
            image_metadata_path=images_path,
            revision="abo-v1",
            limit=1,
        )
        db.commit()

        result, _warnings = evaluate(db, RequirementData(category="laptop"))

        assert {item.product_id for item in result.recommendations} == {
            product.id for product in db.scalars(select(Product))
        }
        abo_row = db.scalar(
            select(ResearchProduct).where(ResearchProduct.dataset_id == "Amazon-Berkeley-Objects")
        )
        details = provenance(abo_row)
        assert details["dataset_name"] == "Amazon Berkeley Objects"
        assert details["license"] == "CC BY 4.0"
        assert details["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
        assert details["external_product_id"] == "B022222222"
        assert details["identifier_label"] == "item_id"
        assert "parent_asin" not in details


@pytest.mark.parametrize("limit", [0, 201, -1])
def test_abo_import_rejects_unapproved_or_invalid_limits(tmp_path, limit):
    catalog = write_jsonl(tmp_path / "abo.jsonl", [abo_record()])
    images = write_images(tmp_path / "images.csv.gz")
    with SessionLocal() as db, pytest.raises(ValueError, match="limit"):
        import_catalog(
            db,
            path=catalog,
            image_metadata_path=images,
            revision="abo-test-v1",
            limit=limit,
        )
