import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import HistoricalPriceReference, Product, ProductOffer, ResearchImportRun, ResearchProduct
from app.services.research.openfacts_importer import import_catalog, map_record
from scripts.download_openfacts_research_sample import download


def source_product(code="3017620422003", *, product_type="food", **overrides):
    value = {
        "code": code,
        "product_type": product_type,
        "product_name": "Chocolate product",
        "product_name_en": "Chocolate product",
        "brands": "Example brand",
        "quantity": "100 g",
        "categories": "Snacks, chocolates",
        "countries": "France",
        "image_front_url": "https://images.openfoodfacts.org/images/products/301/762/042/2003/front_en.400.jpg",
    }
    value.update(overrides)
    return value


def write_response(path, products, retrieved_on="2026-10-29"):
    path.write_text(json.dumps({"retrieved_on": retrieved_on, "products": products}), encoding="utf-8")
    return path


def test_food_mapping_keeps_source_facts_and_does_not_invent_commercial_data():
    mapped = map_record(source_product(), flavor="food", retrieved_on="2026-10-29")

    assert mapped["product"]["name"] == "Chocolate product"
    assert mapped["product"]["category"] == "thuc pham"
    assert mapped["product"]["image_url"].startswith("https://images.openfoodfacts.org/")
    assert mapped["product"]["rating"] is None
    assert mapped["product"]["review_count"] is None
    assert "price" not in mapped["product"]
    assert mapped["metadata"]["content_license"] == "ODbL 1.0"
    assert mapped["metadata"]["image_license"] == "CC BY-SA 4.0"
    assert mapped["metadata"]["source_product_url"].endswith("/product/3017620422003")


def test_open_products_facts_maps_only_explicit_category_and_rejects_wrong_product_type():
    raw = source_product("7613034626844", product_type="product", categories="Laptops")
    raw["image_front_url"] = "https://images.openproductsfacts.org/images/products/761/303/462/6844/front.jpg"
    mapped = map_record(raw, flavor="products", retrieved_on="2026-10-29")

    assert mapped["product"]["category"] == "laptop"
    assert mapped["metadata"]["dataset_name"] == "Open Products Facts"
    assert mapped["metadata"]["image_license"] == "CC BY-SA 4.0"
    accessory = source_product("7613034626845", product_type="product", categories="Laptop screen cleaning wipes")
    assert map_record(accessory, flavor="products", retrieved_on="2026-10-29")["product"]["category"] == "san pham khac"
    with pytest.raises(ValueError, match="unexpected_product_type"):
        map_record(source_product(product_type="food"), flavor="products", retrieved_on="2026-10-29")


@pytest.mark.parametrize("raw,reason", [
    (source_product("bad-code"), "invalid_barcode"),
    (source_product(product_name="", product_name_en=""), "missing_product_name"),
    (source_product(image_front_url="https://attacker.invalid/image.jpg"), None),
])
def test_bad_identity_or_missing_name_rejected_and_untrusted_image_not_used(raw, reason):
    if reason:
        with pytest.raises(ValueError, match=reason):
            map_record(raw, flavor="food", retrieved_on="2026-10-29")
    else:
        mapped = map_record(raw, flavor="food", retrieved_on="2026-10-29")
        assert mapped["product"]["image_url"] is None
        assert mapped["metadata"]["image_license"] is None


def test_import_dry_run_and_apply_are_bounded_idempotent_and_create_no_offers(tmp_path):
    path = write_response(tmp_path / "sample.json", [source_product()])
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        dry = import_catalog(db, path=path, flavor="food", revision="off-v1", dry_run=True)
        assert dry["imported"] == 1 and dry["dry_run"] is True
        assert db.scalar(select(func.count(Product.id))) == 0

        applied = import_catalog(db, path=path, flavor="food", revision="off-v1", dry_run=False)
        db.commit()
        assert applied["imported"] == 1 and applied["offers_created"] == 0
        assert db.scalar(select(func.count(Product.id))) == 1
        assert db.scalar(select(func.count(ResearchProduct.id))) == 1
        assert db.scalar(select(func.count(ResearchImportRun.id))) == 1
        assert db.scalar(select(func.count(ProductOffer.id))) == 0
        assert db.scalar(select(func.count(HistoricalPriceReference.id))) == 0
        imported = db.scalar(select(ResearchProduct))
        from app.services.research.recommendation import provenance
        source_info = provenance(imported)
        assert source_info["barcode"] == "3017620422003"
        assert source_info["content_license"] == "ODbL 1.0"
        assert source_info["image_license"] == "CC BY-SA 4.0"
        assert source_info["source_product_url"].endswith("/product/3017620422003")

        repeated = import_catalog(db, path=path, flavor="food", revision="off-v2", dry_run=False)
        db.commit()
        assert repeated["imported"] == 0 and repeated["duplicates"] == 1
        assert db.scalar(select(func.count(Product.id))) == 1


def test_input_record_limit_is_enforced_before_import(tmp_path):
    path = write_response(tmp_path / "too-many.json", [source_product(str(3000000000000 + i)) for i in range(26)])
    with Session(engine) as db, pytest.raises(ValueError, match="at most 25"):
        import_catalog(db, path=path, flavor="food", revision="off-v1")


def test_imported_open_products_facts_product_is_retrievable_by_research_recommendations(tmp_path):
    raw = source_product("0884116295433", product_type="product", product_name="Example notebook",
                         categories="Laptops", image_front_url=(
                             "https://images.openproductsfacts.org/images/products/088/411/629/5433/front.jpg"))
    path = write_response(tmp_path / "laptop.json", [raw])
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        import_catalog(db, path=path, flavor="products", revision="opf-retrieval-v1", dry_run=False)
        db.flush()
        from app.services.research.recommendation import evaluate, parse_query
        result, _ = evaluate(db, parse_query("laptop"))
        assert len(result.recommendations) == 1
        item = result.recommendations[0]
        assert item.name == "Example notebook"
        assert item.source_mode == "HISTORICAL_RESEARCH"
        assert item.image_url == raw["image_front_url"]
        assert item.price is None
        assert item.research_provenance["dataset_id"] == "OpenProductsFacts"


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.body


def test_downloader_saves_empty_result_as_valid_research_sample(tmp_path):
    output = tmp_path / "empty.json"
    with patch("scripts.download_openfacts_research_sample._contact_email", return_value="test@example.invalid"), \
         patch("scripts.download_openfacts_research_sample.urllib.request.urlopen",
               return_value=FakeResponse(b'{"count":0,"products":[]}')):
        result = download("food", "coffee", 25, output)
    assert result["returned"] == 0
    assert json.loads(output.read_text(encoding="utf-8"))["products"] == []


@pytest.mark.parametrize("error", [TimeoutError("timeout"), HTTPError("https://world.openfoodfacts.org", 503, "unavailable", {}, None)])
def test_downloader_propagates_timeout_and_http_errors_without_partial_file(tmp_path, error):
    output = tmp_path / "failed.json"
    with patch("scripts.download_openfacts_research_sample._contact_email", return_value="test@example.invalid"), \
         patch("scripts.download_openfacts_research_sample.urllib.request.urlopen", side_effect=error), \
         pytest.raises((TimeoutError, HTTPError)):
        download("food", "coffee", 25, output)
    assert not output.exists()
