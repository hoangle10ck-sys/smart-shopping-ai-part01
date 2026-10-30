"""Run from backend: python -m scripts.download_abo_research_sample."""
from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from app.services.research.abo_importer import DATASET_PAGE, PRODUCT_TYPE_CATEGORY

BASE = "https://amazon-berkeley-objects.s3.amazonaws.com"
SHARDS = tuple(f"listings/metadata/listings_{index:x}.json.gz" for index in range(16))
IMAGES = "images/metadata/images.csv.gz"
MAX_SHARD_BYTES = 6 * 1024 * 1024
MAX_IMAGE_BYTES = 7 * 1024 * 1024
MAX_TOTAL_BYTES = 103 * 1024 * 1024
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_SOURCE_RECORDS = 150_000
MAX_LISTINGS = 200
CATEGORY_QUOTAS = {
    "phu kien dien thoai": 25,
    "dien thoai": 25,
    "tai nghe": 25,
    "laptop": 25,
    "ban phim": 25,
    "chuot": 25,
    "phu kien dien tu": 25,
    "man hinh": 25,
}


def download(url: str, target: Path, limit: int) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "amazon-berkeley-objects.s3.amazonaws.com":
        raise ValueError("Download URL is outside the official HTTPS ABO host")
    request = urllib.request.Request(url, headers={"User-Agent": "SmartShoppingAI-research-import/1.0"})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as output:
        if response.status != 200:
            raise RuntimeError(f"ABO returned HTTP {response.status}")
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != parsed.hostname:
            raise ValueError("ABO redirected outside the official HTTPS host")
        etag = response.headers.get("ETag")
        while chunk := response.read(64 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("ABO object exceeded configured download limit")
            digest.update(chunk)
            output.write(chunk)
    return {"url": url, "bytes": size, "etag": etag, "sha256": digest.hexdigest()}


def main() -> int:
    output_dir = Path("data/research/abo")
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "abo-balanced-200.jsonl"
    image_path = output_dir / "images.csv.gz"
    manifest_path = output_dir / "manifest.json"
    selected: dict[str, dict] = {}
    counts: Counter[str] = Counter()
    source_files: list[dict] = []
    total_bytes = 0
    scanned = 0
    expanded = 0

    with tempfile.TemporaryDirectory(prefix="abo-research-") as temp_name:
        temp_dir = Path(temp_name)
        for relative in SHARDS:
            archive = temp_dir / Path(relative).name
            info = download(f"{BASE}/{relative}", archive, MAX_SHARD_BYTES)
            total_bytes += info["bytes"]
            if total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("Total ABO download limit exceeded")
            source_files.append(info)
            with gzip.open(archive, "rb") as stream:
                for line_number, line in enumerate(stream, start=1):
                    expanded += len(line)
                    if len(line) > 2 * 1024 * 1024 or expanded > MAX_EXPANDED_BYTES or line_number > MAX_SOURCE_RECORDS:
                        raise ValueError(f"ABO metadata limit exceeded at shard record {line_number}, expanded bytes={expanded}")
                    scanned += 1
                    try:
                        record = json.loads(line)
                        types = record.get("product_type") or []
                        native_type = next(
                            (item.get("value") for item in types if isinstance(item, dict)
                             and item.get("value") in PRODUCT_TYPE_CATEGORY), None
                        )
                        category = PRODUCT_TYPE_CATEGORY.get(native_type)
                        item_id = record.get("item_id")
                        if category not in CATEGORY_QUOTAS or not isinstance(item_id, str):
                            continue
                        if counts[category] < CATEGORY_QUOTAS[category]:
                            selected.setdefault(item_id, record)
                            counts[category] += 1
                    except (UnicodeError, json.JSONDecodeError, AttributeError, TypeError):
                        continue
                    if len(selected) >= MAX_LISTINGS:
                        break
            if len(selected) >= MAX_LISTINGS:
                break

        if not selected:
            raise RuntimeError("No ABO records matched the bounded category sample")
        image_info = download(f"{BASE}/{IMAGES}", image_path, MAX_IMAGE_BYTES)
        total_bytes += image_info["bytes"]
        if total_bytes > MAX_TOTAL_BYTES:
            image_path.unlink(missing_ok=True)
            raise ValueError("Total ABO download limit exceeded")
        source_files.append(image_info)

    # Preserve deterministic source ordering and newline-delimited native records.
    with catalog_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in selected.values():
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    manifest = {
        "dataset": "Amazon Berkeley Objects",
        "dataset_id": "Amazon-Berkeley-Objects",
        "dataset_url": DATASET_PAGE,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "collection_method": "official public metadata only; no merchant crawling",
        "max_records": MAX_LISTINGS,
        "records_selected": len(selected),
        "records_scanned": scanned,
        "selected_categories": dict(counts),
        "category_quotas": CATEGORY_QUOTAS,
        "downloaded_bytes": total_bytes,
        "source_objects": source_files,
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "images_metadata_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "records_selected", "records_scanned", "selected_categories", "downloaded_bytes", "catalog_sha256"
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
