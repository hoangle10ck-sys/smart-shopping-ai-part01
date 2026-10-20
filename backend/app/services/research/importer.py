"""Bounded native JSONL ingestion. No network, eval, dataset scripts or offers."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.research import HistoricalPriceReference, ResearchImportRun, ResearchProduct
from app.services.normalization.text_normalizer import normalize_product_text

DATASET = "McAuley-Lab/Amazon-Reviews-2023"
CATEGORIES = ("Electronics", "Cell_Phones_and_Accessories")
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024


def source_url(revision: str, category: str) -> str:
    if category not in CATEGORIES or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", revision):
        raise ValueError("Invalid category or revision")
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/raw/meta_categories/meta_{category}.jsonl"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def historical_amount(value) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    # No guessing symbols, ranges, currencies, grouping or exponent notation.
    if not re.fullmatch(r"\d{1,9}(?:\.\d{1,2})?", text):
        return None
    try:
        amount = Decimal(text)
        return format(amount, ".2f") if amount > 0 else None
    except InvalidOperation:
        return None


def safe_image(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme == "https" and url.hostname in {"m.media-amazon.com", "images-na.ssl-images-amazon.com"}
                and not url.username and not url.password and url.port in {None, 443}):
            return value
    except ValueError:
        pass
    return None


def classify(raw: dict, category: str) -> str:
    taxonomy = " ".join(str(v) for v in raw.get("categories", [])).lower()
    title = raw["title"].lower()
    # Accessories take precedence over device names mentioned for compatibility.
    accessory = r"\b(case|cases|cover|covers|protector|protectors|charger|chargers|cable|cables|adapter|adapters|replacement|stand|mount|sleeve|skin|pouch|holder)\b"
    if re.search(accessory, title):
        return "phu kien dien thoai" if category == CATEGORIES[1] else "phu kien dien tu"
    if category == CATEGORIES[1]:
        if any(v in taxonomy for v in ("unlocked cell phones", "cell phones", "smartphones")) and not any(
                v in taxonomy for v in ("accessories", "cases", "chargers", "cables")):
            return "dien thoai"
        # Top-level taxonomy itself contains Accessories. Require device leaf.
        leaf = str((raw.get("categories") or [""])[-1]).lower()
        if leaf in {"unlocked cell phones", "cell phones", "smartphones", "carrier cell phones"}:
            return "dien thoai"
        return "phu kien dien thoai"
    for names, result in [(("headphones", "earbuds", "earphones", "earbud headphones", "over-ear headphones", "on-ear headphones", "headphones & earbuds"), "tai nghe"),
                          (("laptops", "traditional laptops", "notebooks"), "laptop"),
                          (("computer monitors", "monitors"), "man hinh"),
                          (("keyboards",), "ban phim"), (("mice",), "chuot")]:
        if str((raw.get("categories") or [""])[-1]).lower() in names:
            return result
    return "dien tu"


def map_record(raw: dict, category: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("record_not_object")
    asin, title = raw.get("parent_asin"), raw.get("title")
    if not isinstance(asin, str) or not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise ValueError("invalid_parent_asin")
    if not isinstance(title, str) or not 5 <= len(title.strip()) <= 4000:
        raise ValueError("invalid_title")
    taxonomy = raw.get("categories")
    if not isinstance(taxonomy, list) or not taxonomy or not all(isinstance(v, str) for v in taxonomy):
        raise ValueError("missing_taxonomy")
    details = raw.get("details") or {}
    if isinstance(details, str):
        details = json.loads(details)  # some exported loader formats serialize details
    if not isinstance(details, dict):
        raise ValueError("invalid_details")
    specs = {str(k): str(v) for k, v in details.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}
    # Only unambiguous property aliases, no title capacity/brand inference.
    for native, normalized in {"RAM": "ram", "Ram Memory Installed Size": "ram",
                               "Memory Storage Capacity": "storage", "Hard Drive Size": "storage"}.items():
        if native in specs:
            specs[normalized] = specs[native]
    images = raw.get("images") or []
    image_url = next((safe_image(img.get("hi_res")) or safe_image(img.get("large"))
                      for img in images if isinstance(img, dict) and
                      (safe_image(img.get("hi_res")) or safe_image(img.get("large")))), None) if isinstance(images, list) else None
    rating = raw.get("average_rating")
    rating = float(rating) if isinstance(rating, (float, int)) and not isinstance(rating, bool) and math.isfinite(rating) and 0 <= rating <= 5 else None
    count = raw.get("rating_number")
    count = count if type(count) is int and 0 <= count <= 2**31-1 else None
    return dict(external_product_id=asin, amount=historical_amount(raw.get("price")),
                product=dict(name=title.strip(), normalized_name=normalize_product_text(title),
                             category=classify(raw, category), brand=specs.get("Brand"),
                             model=specs.get("Item model number"), specifications=specs,
                             image_url=image_url, rating=rating, review_count=count),
                metadata={key: raw.get(key) for key in ("main_category", "categories", "features", "description", "store", "price")})


def import_catalog(db: Session, *, path: Path, revision: str, category: str,
                   dataset: str = DATASET, limit: int = 75, dry_run: bool = False,
                   category_quotas: dict[str, int] | None = None) -> dict:
    if dataset != DATASET or category not in CATEGORIES or not 1 <= limit <= 10000:
        raise ValueError("Unsupported dataset/category or limit (1..10000)")
    if category_quotas is not None and (not isinstance(category_quotas, dict) or not category_quotas or any(
            key not in {"dien thoai", "laptop", "tai nghe", "man hinh", "ban phim", "chuot", "dien tu", "phu kien dien thoai", "phu kien dien tu"}
            or type(value) is not int or not 1 <= value <= 1000 for key, value in category_quotas.items())):
        raise ValueError("Invalid mapped category quotas")
    url = source_url(revision, category)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Input must be a local file <=64 MiB")
    digest = checksum(path)
    report = dict(dataset=dataset, revision=revision, category=category, source_url=url,
                  input_sha256=digest, dry_run=dry_run, scanned=0, selected=0,
                  imported=0, duplicates=0, skipped=0, errors={}, price_available=0,
                  selection="first N valid unique identities within category prefix")
    selected_categories = {}
    if category_quotas:
        report.update(selection="first valid unique identities per mapped-category quota; prefix-biased",
                      category_quotas=category_quotas, selected_categories=selected_categories, outside_quota=0)
    seen = set()
    total_bytes = 0
    opener = gzip.open if path.suffix == ".gz" else open
    # Atomic savepoint, including truncation/decompression errors. Caller owns commit.
    with db.begin_nested(), opener(path, "rb") as stream:
        for line_number in range(1, 100001):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            total_bytes += len(line)
            if len(line) > MAX_LINE_BYTES or total_bytes > MAX_FILE_BYTES:
                raise ValueError("Line/decompressed byte limit exceeded")
            report["scanned"] += 1
            try:
                raw = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError("nonfinite_json")))
                mapped = map_record(raw, category)
            except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
                report["skipped"] += 1
                reason = str(exc)[:120]
                report["errors"][reason] = report["errors"].get(reason, 0) + 1
                continue
            identity = mapped["external_product_id"]
            mapped_category = mapped["product"]["category"]
            if category_quotas and selected_categories.get(mapped_category, 0) >= category_quotas.get(mapped_category, 0):
                report["outside_quota"] += 1
                continue
            if identity in seen:
                report["duplicates"] += 1
                continue
            seen.add(identity)
            report["selected"] += 1
            selected_categories[mapped_category] = selected_categories.get(mapped_category, 0) + 1
            line_hash = hashlib.sha256(line).hexdigest()
            prior = db.scalar(select(ResearchProduct).where(ResearchProduct.dataset_id == dataset,
                ResearchProduct.revision == revision, ResearchProduct.external_product_id == identity))
            if prior:
                if prior.record_sha256 != line_hash:
                    report["skipped"] += 1
                    report["errors"]["identity_content_conflict"] = report["errors"].get("identity_content_conflict", 0) + 1
                else:
                    report["duplicates"] += 1
            else:
                report["imported"] += 1
                report["price_available"] += mapped["amount"] is not None
                if not dry_run:
                    product = Product(**mapped["product"])
                    db.add(product)
                    db.flush()
                    research = ResearchProduct(product_id=product.id, dataset_id=dataset, revision=revision,
                        external_product_id=identity, source_category=category, source_url=url,
                        input_sha256=digest, record_sha256=line_hash, line_number=line_number,
                        metadata_fields=mapped["metadata"])
                    db.add(research)
                    db.flush()
                    if mapped["amount"] is not None:
                        db.add(HistoricalPriceReference(research_product_id=research.id, amount=mapped["amount"],
                            currency="USD", source=url, reference_year=2023, price_observed_at=None,
                            provenance={"native_field": "price", "record_sha256": line_hash,
                                        "currency_basis": "official dataset card: Price in US dollars (at time of crawling)"}))
            if report["selected"] >= limit:
                break
        if not dry_run:
            db.add(ResearchImportRun(dataset_id=dataset, revision=revision, input_sha256=digest, report=report))
    return report
