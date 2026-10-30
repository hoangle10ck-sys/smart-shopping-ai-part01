"""Run from backend: python -m scripts.download_abo_research_extension."""
from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from app.services.research.abo_importer import (
    DATASET_PAGE,
    LICENSE_NAME,
    LICENSE_URL,
    PRODUCT_TYPE_CATEGORY,
    load_image_paths,
)
from scripts.download_abo_research_sample import (
    BASE,
    MAX_EXPANDED_BYTES,
    MAX_SHARD_BYTES,
    MAX_SOURCE_RECORDS,
    MAX_TOTAL_BYTES,
    SHARDS,
    download,
)

MAX_EXTENSION_COUNT = 64
SOURCE_SAMPLE = Path("data/research/abo/abo-balanced-200.jsonl")
IMAGE_METADATA = Path("data/research/abo/images.csv.gz")
OUTPUT_DIR = Path("data/research/abo-extension-64")
CATEGORY_QUOTAS = {
    "giày": 16,
    "thực phẩm": 12,
    "đồ gia dụng": 12,
    "thú cưng": 8,
    "đồ thể thao": 7,
    "tivi": 5,
    "tủ lạnh": 4,
}


def category_for(record: object) -> str | None:
    if not isinstance(record, dict):
        return None
    product_types = record.get("product_type")
    if not isinstance(product_types, list):
        return None
    return next((PRODUCT_TYPE_CATEGORY[item.get("value")] for item in product_types
                 if isinstance(item, dict) and item.get("value") in PRODUCT_TYPE_CATEGORY
                 and PRODUCT_TYPE_CATEGORY[item["value"]] in CATEGORY_QUOTAS), None)


def select_record(
    record: object,
    *,
    existing_ids: set[str],
    selected: dict[str, dict],
    counts: Counter[str],
) -> bool:
    """Select a source record once, under the fixed category quotas."""
    if not isinstance(record, dict):
        return False
    item_id = record.get("item_id")
    category = category_for(record)
    if (not isinstance(item_id, str) or item_id in existing_ids or item_id in selected
            or category is None or counts[category] >= CATEGORY_QUOTAS[category]):
        return False
    selected[item_id] = record
    counts[category] += 1
    return True


def main() -> int:
    if sum(CATEGORY_QUOTAS.values()) != MAX_EXTENSION_COUNT:
        raise RuntimeError("Extension quota must stay at 64 records")
    if not SOURCE_SAMPLE.is_file() or not IMAGE_METADATA.is_file():
        raise FileNotFoundError("The approved ABO sample and image metadata must exist")
    existing_ids = {
        row["item_id"]
        for line in SOURCE_SAMPLE.read_text(encoding="utf-8").splitlines()
        if (row := json.loads(line)).get("item_id")
    }
    image_paths = load_image_paths(IMAGE_METADATA)
    selected: dict[str, dict] = {}
    counts: Counter[str] = Counter()
    source_files: list[dict] = []
    total_bytes = 0
    expanded = 0
    scanned = 0

    with tempfile.TemporaryDirectory(prefix="abo-extension-") as temp_name:
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
                    if (len(line) > 2 * 1024 * 1024 or expanded > MAX_EXPANDED_BYTES
                            or line_number > MAX_SOURCE_RECORDS):
                        raise ValueError("ABO source scan limit exceeded")
                    scanned += 1
                    try:
                        record = json.loads(line)
                    except (UnicodeError, json.JSONDecodeError):
                        continue
                    image_id = record.get("main_image_id") if isinstance(record, dict) else None
                    if isinstance(image_id, str) and image_id in image_paths:
                        select_record(record, existing_ids=existing_ids, selected=selected, counts=counts)
        if len(selected) != MAX_EXTENSION_COUNT:
            raise RuntimeError(f"Only {len(selected)}/64 image-backed records matched category quotas")

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=False)
    catalog_path = OUTPUT_DIR / "abo-extension-64.jsonl"
    with catalog_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in selected.values():
            output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    manifest = {
        "dataset": "Amazon Berkeley Objects",
        "dataset_id": "Amazon-Berkeley-Objects",
        "dataset_url": DATASET_PAGE,
        "license": LICENSE_NAME,
        "license_url": LICENSE_URL,
        "collection_method": "official public metadata only; no merchant crawling",
        "extension_of_sha256": hashlib.sha256(SOURCE_SAMPLE.read_bytes()).hexdigest(),
        "max_records": MAX_EXTENSION_COUNT,
        "records_selected": len(selected),
        "records_scanned": scanned,
        "selected_categories": dict(counts),
        "category_quotas": CATEGORY_QUOTAS,
        "downloaded_bytes": total_bytes,
        "source_objects": source_files,
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "images_metadata_sha256": hashlib.sha256(IMAGE_METADATA.read_bytes()).hexdigest(),
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: manifest[key] for key in (
        "records_selected", "records_scanned", "selected_categories", "downloaded_bytes", "catalog_sha256"
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
