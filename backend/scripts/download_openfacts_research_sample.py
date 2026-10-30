"""Download one small Open Food Facts/Open Products Facts Research sample.

Run from backend with: python -m scripts.download_openfacts_research_sample --flavor food
The script performs one read-only request and never visits merchant sites.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app.services.research.openfacts_importer import DATASETS, MAX_IMPORT_COUNT

REPO_ROOT = Path(__file__).resolve().parents[2]
FIELDS = "code,product_type,product_name,product_name_en,brands,quantity,categories,countries,image_front_url,image_url"


def _contact_email() -> str:
    value = os.environ.get("OPENFACTS_CONTACT_EMAIL", "").strip()
    if value:
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            return value
        raise RuntimeError("OPENFACTS_CONTACT_EMAIL must be a valid address; value is not displayed.")
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            candidate = line.strip()
            if candidate.startswith("OPENFACTS_CONTACT_EMAIL="):
                value = candidate.partition("=")[2].strip().strip("\"'")
                if value:
                    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                        return value
                    raise RuntimeError("OPENFACTS_CONTACT_EMAIL must be a valid address; value is not displayed.")
    raise RuntimeError("Set OPENFACTS_CONTACT_EMAIL in the ignored root .env file before downloading.")


def download(flavor: str, query: str, page_size: int, output: Path) -> dict:
    if flavor not in DATASETS or not 1 <= page_size <= MAX_IMPORT_COUNT:
        raise ValueError("Invalid flavor or page size (1..25)")
    query = " ".join(query.split()).strip()
    if not query or len(query) > 100:
        raise ValueError("Query must contain 1..100 characters")
    source = DATASETS[flavor]
    params = urllib.parse.urlencode({
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "fields": FIELDS,
    })
    url = f"{source['api']}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"SmartShoppingAI/0.1 (+contact: {_contact_email()})",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"Open Facts returned HTTP {response.status}")
        body = response.read(5 * 1024 * 1024 + 1)
    if len(body) > 5 * 1024 * 1024:
        raise ValueError("Open Facts response exceeded 5 MiB")
    document = json.loads(body)
    products = document.get("products") if isinstance(document, dict) else None
    if not isinstance(products, list) or len(products) > page_size:
        raise ValueError("Unexpected Open Facts response shape or page size")
    expected_types = {"food": {"food"}, "products": {"product", "other"}}[flavor]
    products = [item for item in products if isinstance(item, dict) and item.get("product_type") in expected_types]
    document = {
        "dataset_id": source["id"],
        "dataset_name": source["name"],
        "source_url": url,
        "source_homepage": source["page"],
        "query": query,
        "retrieved_on": datetime.now(timezone.utc).date().isoformat(),
        "response_count": len(products),
        "products": products,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "dataset": source["id"],
        "query": query,
        "source_host": urllib.parse.urlparse(source["api"]).hostname,
        "returned": len(products),
        "with_image": sum(bool(item.get("image_front_url") or item.get("image_url")) for item in products),
        "output": str(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flavor", required=True, choices=tuple(DATASETS))
    parser.add_argument("--query", default=None)
    parser.add_argument("--limit", type=int, default=MAX_IMPORT_COUNT, choices=range(1, MAX_IMPORT_COUNT + 1))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    query = args.query or ("coffee" if args.flavor == "food" else "laptop")
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:40] or "sample"
    output = args.output or Path("data/research/openfacts") / f"{args.flavor}-{slug}-{datetime.now(timezone.utc).date().isoformat()}.json"
    result = download(args.flavor, query, args.limit, output)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
