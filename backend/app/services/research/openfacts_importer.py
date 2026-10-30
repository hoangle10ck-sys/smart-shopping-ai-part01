"""Bounded, offline importer for Open Food Facts family research catalogs."""
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.research import ResearchImportRun, ResearchProduct
from app.services.normalization.text_normalizer import normalize_product_text

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_IMPORT_COUNT = 25
DATASETS = {
    "food": {
        "id": "OpenFoodFacts",
        "name": "Open Food Facts",
        "host": "world.openfoodfacts.org",
        "image_host": "images.openfoodfacts.org",
        "page": "https://world.openfoodfacts.org/",
        "api": "https://world.openfoodfacts.org/cgi/search.pl",
        "content_license": "ODbL 1.0",
        "content_license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "database_license": "Database Contents License (DbCL) v1.0",
        "image_license": "CC BY-SA 4.0",
        "image_license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    },
    "products": {
        "id": "OpenProductsFacts",
        "name": "Open Products Facts",
        "host": "world.openproductsfacts.org",
        "image_host": "images.openproductsfacts.org",
        "page": "https://world.openproductsfacts.org/",
        "api": "https://world.openproductsfacts.org/cgi/search.pl",
        "content_license": "ODbL 1.0",
        "content_license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "database_license": "Database Contents License (DbCL) v1.0",
        "image_license": "CC BY-SA 4.0",
        "image_license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
    },
}
_BARCODE = re.compile(r"^\d{8,14}$")
_REVISION = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: object, limit: int = 1000) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split()).strip()
    return html.unescape(value)[:limit] or None


def _safe_image(value: object, expected_host: str) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
        if (parsed.scheme != "https" or parsed.hostname != expected_host or parsed.port not in (None, 443)
                or parsed.username or parsed.password or not parsed.path.startswith("/")):
            return None
    except ValueError:
        return None
    return value[:2000]


def _category(flavor: str, categories: str | None) -> str:
    if flavor == "food":
        return "thuc pham"
    tags = {re.sub(r"[^a-z0-9-]+", "-", item.strip().lower()).strip("-")
            for item in (categories or "").split(",") if item.strip()}
    mappings = (
        ({"laptop", "laptops", "notebook-computer", "notebook-computers"}, "laptop"),
        ({"smartphone", "smartphones", "mobile-phone", "mobile-phones", "cell-phone"}, "dien thoai"),
        ({"headphone", "headphones", "earphone", "earphones", "earbud", "earbuds"}, "tai nghe"),
        ({"television", "televisions", "smart-tv", "smart-tvs"}, "tivi"),
        ({"refrigerator", "refrigerators", "fridge", "fridges"}, "tu lanh"),
        ({"monitor", "monitors", "computer-screen", "computer-screens"}, "man hinh"),
        ({"keyboard", "keyboards"}, "ban phim"),
        ({"mouse", "mice", "pointing-device"}, "chuot"),
        ({"home-appliance", "home-appliances", "household-appliance"}, "do gia dung"),
        ({"electronics", "electronic-device", "electronic-devices"}, "dien tu"),
    )
    for exact_tags, category in mappings:
        if tags & exact_tags:
            return category
    return "san pham khac"


def map_record(raw: object, *, flavor: str, retrieved_on: str) -> dict:
    """Map one source record without deriving price, stock, reviews, or rating."""
    if flavor not in DATASETS:
        raise ValueError("unsupported_dataset")
    if not isinstance(raw, dict):
        raise ValueError("record_not_object")
    code = raw.get("code")
    if not isinstance(code, str) or not _BARCODE.fullmatch(code):
        raise ValueError("invalid_barcode")
    name = _text(raw.get("product_name")) or _text(raw.get("product_name_en"))
    if not name:
        raise ValueError("missing_product_name")
    source = DATASETS[flavor]
    product_type = raw.get("product_type")
    expected_types = {"food": {"food"}, "products": {"product", "other"}}[flavor]
    if product_type not in expected_types:
        raise ValueError("unexpected_product_type")
    brand = _text(raw.get("brands"))
    quantity = _text(raw.get("quantity"))
    categories = _text(raw.get("categories"))
    countries = _text(raw.get("countries"))
    image = _safe_image(raw.get("image_front_url") or raw.get("image_url"), source["image_host"])
    specs = {key: value for key, value in {
        "quantity": quantity,
        "source_categories": categories,
        "countries": countries,
    }.items() if value}
    product_url = f"https://{source['host']}/product/{code}"
    product = {
        "name": name,
        "normalized_name": normalize_product_text(name),
        "category": _category(flavor, categories),
        "brand": brand,
        "model": None,
        "specifications": specs,
        "image_url": image,
        "rating": None,
        "review_count": None,
    }
    metadata = {
        "dataset_name": source["name"],
        "dataset_url": source["page"],
        "source_product_url": product_url,
        "source_api_url": source["api"],
        "product_type": product_type,
        "barcode": code,
        "identifier_label": "barcode",
        "retrieved_on": retrieved_on,
        "content_license": source["content_license"],
        "content_license_url": source["content_license_url"],
        "database_license": source["database_license"],
        "image_license": source["image_license"] if image else None,
        "image_license_url": source["image_license_url"] if image else None,
        "attribution": source["name"],
        "price_imported": False,
        "offers_imported": False,
        "rating_imported": False,
        "review_count_imported": False,
        **{key: value for key, value in {"brands": brand, "quantity": quantity,
                                         "categories": categories, "countries": countries}.items() if value},
    }
    return {
        "external_product_id": code,
        "product": product,
        "source_category": categories or product["category"],
        "source_url": product_url,
        "metadata": metadata,
    }


def import_catalog(db: Session, *, path: Path, flavor: str, revision: str,
                   limit: int = MAX_IMPORT_COUNT, dry_run: bool = True) -> dict:
    if flavor not in DATASETS or not _REVISION.fullmatch(revision) or not 1 <= limit <= MAX_IMPORT_COUNT:
        raise ValueError("Invalid source, revision, or limit (1..25)")
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Open Facts input must be a local JSON file <=8 MiB")
    raw_bytes = path.read_bytes()
    document = json.loads(raw_bytes, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    products = document.get("products") if isinstance(document, dict) else None
    if not isinstance(products, list) or len(products) > MAX_IMPORT_COUNT:
        raise ValueError("Open Facts response must contain at most 25 products")
    source = DATASETS[flavor]
    retrieved_on = _text(document.get("retrieved_on")) if isinstance(document, dict) else None
    if not retrieved_on:
        retrieved_on = "unknown"
    digest = hashlib.sha256(raw_bytes).hexdigest()
    report = {"dataset": source["id"], "revision": revision, "input_sha256": digest,
              "dry_run": dry_run, "scanned": len(products), "selected": 0, "imported": 0,
              "duplicates": 0, "skipped": 0, "errors": {}, "images": 0,
              "prices_created": 0, "offers_created": 0}
    seen: set[str] = set()
    with db.begin_nested():
        for index, raw in enumerate(products, start=1):
            try:
                mapped = map_record(raw, flavor=flavor, retrieved_on=retrieved_on)
            except (TypeError, ValueError) as exc:
                report["skipped"] += 1
                reason = str(exc)[:80]
                report["errors"][reason] = report["errors"].get(reason, 0) + 1
                continue
            identity = mapped["external_product_id"]
            if identity in seen:
                report["duplicates"] += 1
                continue
            seen.add(identity)
            report["selected"] += 1
            report["images"] += bool(mapped["product"]["image_url"])
            existing = db.scalar(select(ResearchProduct).where(
                ResearchProduct.dataset_id == source["id"],
                ResearchProduct.external_product_id == identity,
            ).limit(1))
            if existing:
                report["duplicates"] += 1
                continue
            report["imported"] += 1
            if not dry_run:
                product = Product(**mapped["product"])
                db.add(product)
                db.flush()
                record_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False,
                                                        separators=(",", ":")).encode()).hexdigest()
                db.add(ResearchProduct(
                    product_id=product.id, dataset_id=source["id"], revision=revision,
                    external_product_id=identity, source_category=mapped["source_category"],
                    source_url=mapped["source_url"], input_sha256=digest, record_sha256=record_hash,
                    line_number=index, metadata_fields=mapped["metadata"],
                ))
            if report["selected"] >= limit:
                break
        if not dry_run:
            db.add(ResearchImportRun(dataset_id=source["id"], revision=revision,
                                     input_sha256=digest, report=report))
    return report
