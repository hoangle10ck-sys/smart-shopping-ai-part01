"""Bounded importer for the CC BY 4.0 Amazon Berkeley Objects catalog."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.research import ResearchImportRun, ResearchProduct
from app.services.normalization.text_normalizer import normalize_product_text

DATASET = "Amazon-Berkeley-Objects"
DATASET_PAGE = "https://amazon-berkeley-objects.s3.amazonaws.com/index.html"
DATASET_METADATA_URL = "https://amazon-berkeley-objects.s3.amazonaws.com/listings/metadata/"
LICENSE_NAME = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_IMPORT_COUNT = 200
MAX_IMAGE_ROWS = 500_000

# Map explicit source product types to specific Research categories.
PRODUCT_TYPE_CATEGORY = {
    "CELLULAR_PHONE_CASE": "phu kien dien thoai",
    "PHONE_ACCESSORY": "phu kien dien thoai",
    "PORTABLE_ELECTRONIC_DEVICE_COVER": "phu kien dien thoai",
    "CELLULAR_PHONE": "dien thoai",
    "SMARTPHONE": "dien thoai",
    "HEADPHONES": "tai nghe",
    "NOTEBOOK_COMPUTER": "laptop",
    "KEYBOARDS": "ban phim",
    "INPUT_MOUSE": "chuot",
    "COMPUTER_ADD_ON": "phu kien dien tu",
    "COMPUTER_COMPONENT": "phu kien dien tu",
    "COMPUTER_INPUT_DEVICE": "phu kien dien tu",
    "COMPUTER_INPUT_DEVICE_ACCESSORY": "phu kien dien tu",
    "WIRELESS_ACCESSORY": "phu kien dien tu",
    "TELEVISION": "tivi",
    "MONITOR": "man hinh",
    "PERSONAL_COMPUTER": "dien tu",
    "COMPUTER": "dien tu",
    "CONSUMER_ELECTRONICS": "dien tu",
    "OFFICE_ELECTRONICS": "dien tu",
    "CAMERA": "dien tu",
    "SHOES": "giày",
    "GROCERY": "thực phẩm",
    "HOME": "đồ gia dụng",
    "HOME_BED_AND_BATH": "đồ gia dụng",
    "HOME_FURNITURE_AND_DECOR": "đồ gia dụng",
    "PET_SUPPLIES": "thú cưng",
    "SPORTING_GOODS": "đồ thể thao",
    "REFRIGERATOR": "tủ lạnh",
}
_SAFE_IMAGE_PATH = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{8}\.(?:jpg|png)$")
_SAFE_IMAGE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_SAFE_REVISION = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_image_paths(path: Path) -> dict[str, str]:
    """Read only validated image IDs and relative paths from the ABO CSV."""
    if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Image metadata must be a local file <=16 MiB")
    mapping: dict[str, str] = {}
    expanded = 0
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as binary:
        import io

        with io.TextIOWrapper(binary, encoding="utf-8", newline="") as stream:
            for row_number, row in enumerate(csv.DictReader(stream), start=1):
                expanded += sum(len(str(value or "")) for value in row.values())
                if expanded > MAX_FILE_BYTES or row_number > MAX_IMAGE_ROWS:
                    raise ValueError("Image metadata row/byte limit exceeded")
                image_id = row.get("image_id", "")
                image_path = row.get("path", "")
                if _SAFE_IMAGE_ID.fullmatch(image_id) and _SAFE_IMAGE_PATH.fullmatch(image_path):
                    mapping.setdefault(image_id, image_path)
    return mapping


def _text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text[:4000] if text else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _localized(value: object) -> str | None:
    if isinstance(value, str):
        return _text(value)
    if not isinstance(value, list):
        return _text(value)
    candidates = [item for item in value if isinstance(item, dict)]
    candidates.sort(
        key=lambda item: (
            0 if item.get("language_tag") == "en_US" else
            1 if str(item.get("language_tag", "")).startswith("en_") else 2
        )
    )
    for item in candidates:
        text = _text(item.get("value"))
        if text:
            return text
    return None


def _measure(value: object) -> str | None:
    if isinstance(value, list):
        parts = [_measure(item) for item in value]
        return "; ".join(part for part in parts if part) or None
    if not isinstance(value, dict):
        return _text(value)
    if "value" in value:
        amount = _text(value.get("value"))
        unit = _text(value.get("unit"))
        return f"{amount} {unit}".strip() if amount else None
    parts = []
    for key in ("length", "width", "height", "depth"):
        if key in value:
            rendered = _measure(value[key])
            if rendered:
                parts.append(f"{key}: {rendered}")
    return ", ".join(parts) or None


def map_record(raw: object, image_paths: dict[str, str]) -> dict:
    """Map one native ABO listing without inventing ratings, prices, or offers."""
    if not isinstance(raw, dict):
        raise ValueError("record_not_object")
    item_id = raw.get("item_id")
    if not isinstance(item_id, str) or not re.fullmatch(r"[A-Z0-9]{10}", item_id):
        raise ValueError("invalid_item_id")
    name = _localized(raw.get("item_name"))
    if not name or len(name) > 4000:
        raise ValueError("missing_item_name")
    product_types = raw.get("product_type")
    if not isinstance(product_types, list):
        raise ValueError("missing_product_type")
    native_type = next(
        (item.get("value") for item in product_types if isinstance(item, dict)
         and item.get("value") in PRODUCT_TYPE_CATEGORY),
        None,
    )
    if native_type is None:
        raise ValueError("unsupported_product_type")

    image_id = raw.get("main_image_id")
    image_path = image_paths.get(image_id) if isinstance(image_id, str) else None
    image_url = (
        f"https://amazon-berkeley-objects.s3.amazonaws.com/images/small/{quote(image_path, safe='/')}"
        if image_path and _SAFE_IMAGE_PATH.fullmatch(image_path)
        else None
    )

    specs: dict[str, object] = {"product_type": native_type}
    field_map = {
        "model_number": "model_number",
        "model_name": "model_name",
        "model_year": "model_year",
        "color": "color",
        "material": "material",
        "style": "style",
    }
    for source_key, output_key in field_map.items():
        rendered = _localized(raw.get(source_key))
        if rendered:
            specs[output_key] = rendered
    dimensions = _measure(raw.get("item_dimensions"))
    weight = _measure(raw.get("item_weight"))
    if dimensions:
        specs["dimensions"] = dimensions
    if weight:
        specs["weight"] = weight
    bullet_points = raw.get("bullet_point")
    highlights = [
        text for item in bullet_points if (text := _localized([item]))
    ] if isinstance(bullet_points, list) else []
    if highlights:
        specs["highlights"] = "; ".join(highlights[:12])[:4000]

    product = dict(
        name=name,
        normalized_name=normalize_product_text(name),
        category=PRODUCT_TYPE_CATEGORY[native_type],
        brand=_localized(raw.get("brand")),
        model=_localized(raw.get("model_name")) or _localized(raw.get("model_number")),
        specifications=specs,
        image_url=image_url,
        rating=None,
        review_count=None,
    )
    metadata = {
        "dataset_name": "Amazon Berkeley Objects",
        "license": LICENSE_NAME,
        "license_url": LICENSE_URL,
        "dataset_url": DATASET_PAGE,
        "native_product_type": native_type,
        "domain_name": _text(raw.get("domain_name")),
        "marketplace": _text(raw.get("marketplace")),
        "country": _text(raw.get("country")),
        "main_image_id": image_id if isinstance(image_id, str) else None,
        "image_path": image_path,
    }
    return {
        "external_product_id": item_id,
        "product": product,
        "source_category": native_type,
        "source_url": DATASET_METADATA_URL,
        "historical_price": None,
        "metadata": metadata,
    }


def import_catalog(
    db: Session,
    *,
    path: Path,
    image_metadata_path: Path,
    revision: str,
    limit: int = MAX_IMPORT_COUNT,
    category_quotas: dict[str, int] | None = None,
    dry_run: bool = False,
) -> dict:
    if not _SAFE_REVISION.fullmatch(revision) or not 1 <= limit <= MAX_IMPORT_COUNT:
        raise ValueError("Invalid ABO revision or limit (1..200)")
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("ABO input must be a local file <=64 MiB")
    allowed_categories = set(PRODUCT_TYPE_CATEGORY.values())
    if category_quotas is not None and (
        not isinstance(category_quotas, dict) or not category_quotas
        or any(key not in allowed_categories or type(value) is not int or not 1 <= value <= MAX_IMPORT_COUNT
               for key, value in category_quotas.items())
    ):
        raise ValueError("Invalid ABO mapped-category quota")

    image_paths = load_image_paths(image_metadata_path)
    digest = checksum(path)
    report = dict(
        dataset=DATASET,
        revision=revision,
        source_url=DATASET_PAGE,
        license=LICENSE_NAME,
        input_sha256=digest,
        image_metadata_sha256=checksum(image_metadata_path),
        dry_run=dry_run,
        scanned=0,
        selected=0,
        imported=0,
        duplicates=0,
        skipped=0,
        errors={},
        categories={},
        prices_created=0,
        offers_created=0,
        image_paths_available=len(image_paths),
    )
    seen: set[str] = set()
    total_bytes = 0
    opener = gzip.open if path.suffix == ".gz" else open
    with db.begin_nested(), opener(path, "rb") as stream:
        for line_number in range(1, 100_001):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            total_bytes += len(line)
            if len(line) > MAX_LINE_BYTES or total_bytes > MAX_FILE_BYTES:
                raise ValueError("ABO line/decompressed byte limit exceeded")
            report["scanned"] += 1
            try:
                raw = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite_json")))
                mapped = map_record(raw, image_paths)
            except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
                report["skipped"] += 1
                reason = str(exc)[:120]
                report["errors"][reason] = report["errors"].get(reason, 0) + 1
                continue

            identity = mapped["external_product_id"]
            category = mapped["product"]["category"]
            if category_quotas and report["categories"].get(category, 0) >= category_quotas.get(category, 0):
                continue
            if identity in seen:
                report["duplicates"] += 1
                continue
            seen.add(identity)
            report["selected"] += 1
            report["categories"][category] = report["categories"].get(category, 0) + 1
            record_hash = hashlib.sha256(line.rstrip(b"\r\n")).hexdigest()
            prior = db.scalar(
                select(ResearchProduct).where(
                    ResearchProduct.dataset_id == DATASET,
                    ResearchProduct.revision == revision,
                    ResearchProduct.external_product_id == identity,
                )
            )
            if prior:
                if prior.record_sha256 == record_hash:
                    report["duplicates"] += 1
                else:
                    report["skipped"] += 1
                    report["errors"]["identity_content_conflict"] = report["errors"].get("identity_content_conflict", 0) + 1
            else:
                report["imported"] += 1
                if not dry_run:
                    product = Product(**mapped["product"])
                    db.add(product)
                    db.flush()
                    db.add(
                        ResearchProduct(
                            product_id=product.id,
                            dataset_id=DATASET,
                            revision=revision,
                            external_product_id=identity,
                            source_category=mapped["source_category"],
                            source_url=mapped["source_url"],
                            input_sha256=digest,
                            record_sha256=record_hash,
                            line_number=line_number,
                            metadata_fields=mapped["metadata"],
                        )
                    )
            if report["selected"] >= limit:
                break
        if not dry_run:
            db.add(ResearchImportRun(dataset_id=DATASET, revision=revision, input_sha256=digest, report=report))
    return report
