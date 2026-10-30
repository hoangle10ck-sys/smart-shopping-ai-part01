"""Read JSONL product image records on stdin and verify image bytes, without DB writes."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit

from app.services.extraction.product_image_resolver import ProductImageResolver

ALLOWED_HOSTS = {
    "Amazon-Berkeley-Objects": "amazon-berkeley-objects.s3.amazonaws.com",
    "OpenProductsFacts": "images.openproductsfacts.org",
    "OpenFoodFacts": "images.openfoodfacts.org",
}


def source_rejection(row: dict) -> str | None:
    dataset = row.get("dataset_id")
    metadata = row.get("metadata_fields") or {}
    image_url = row.get("image_url")
    if not image_url:
        return "IMAGE_MISSING"
    host = ALLOWED_HOSTS.get(dataset)
    identifier = str(row.get("external_product_id") or "").strip()
    source_url = metadata.get("source_product_url") or metadata.get("dataset_url") or row.get("source_url")
    if not host or not identifier:
        return "IMAGE_IDENTITY_UNVERIFIED"
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        return "IMAGE_SOURCE_UNVERIFIED"
    if dataset in {"OpenProductsFacts", "OpenFoodFacts"}:
        if metadata.get("identifier_label") != "barcode" or not identifier.isdecimal():
            return "IMAGE_IDENTITY_UNVERIFIED"
        if not valid_gtin(identifier):
            return "IMAGE_IDENTITY_UNVERIFIED"
        if not metadata.get("image_license"):
            return "IMAGE_SOURCE_UNVERIFIED"
    elif dataset == "Amazon-Berkeley-Objects":
        if not (metadata.get("image_path") or metadata.get("main_image_id")):
            return "IMAGE_IDENTITY_UNVERIFIED"
        if not metadata.get("license"):
            return "IMAGE_SOURCE_UNVERIFIED"
    parsed = urlsplit(image_url)
    if parsed.scheme != "https" or parsed.hostname != host:
        return "IMAGE_SOURCE_UNVERIFIED"
    return None


def valid_gtin(value: str) -> bool:
    if len(value) not in {8, 12, 13, 14} or not value.isdecimal():
        return False
    digits = [int(char) for char in value]
    check = digits.pop()
    weighted = sum(digit * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(digits)))
    return (10 - weighted % 10) % 10 == check


async def main() -> int:
    rows = [json.loads(line) for line in sys.stdin if line.strip()]
    resolver = ProductImageResolver(concurrency=4)
    resolver.timeout = 8.0
    semaphore = asyncio.Semaphore(4)
    reasons: dict[int, str] = {}
    hashes: dict[int, str] = {}

    async def verify(row: dict) -> None:
        product_id = int(row["product_id"])
        reason = source_rejection(row)
        if reason:
            reasons[product_id] = reason
            return
        async with semaphore:
            result = await resolver.verify_image(
                row["image_url"], allowed_hosts={ALLOWED_HOSTS[row["dataset_id"]]}
            )
        if result.get("accepted"):
            hashes[product_id] = result["content_sha256"]
        else:
            probe_reason = result.get("reason")
            reasons[product_id] = (
                "IMAGE_INVALID_CONTENT"
                if probe_reason in {"non_raster_mime", "invalid_or_tiny_raster", "image_too_large"}
                else "IMAGE_UNAVAILABLE"
                if str(probe_reason).startswith("http_") or probe_reason in {"redirect_limit", "redirect_outside_approved_host"}
                else "IMAGE_SOURCE_UNVERIFIED"
            )

    async with resolver.session():
        await asyncio.gather(*(verify(row) for row in rows))

    by_hash: dict[str, list[int]] = defaultdict(list)
    for product_id, digest in hashes.items():
        by_hash[digest].append(product_id)
    duplicates = [sorted(ids) for ids in by_hash.values() if len(ids) > 1]
    for group in duplicates:
        for product_id in group:
            reasons[product_id] = "IMAGE_DUPLICATE_IDENTITY_CONFLICT"
            hashes.pop(product_id, None)
    summary = {
        "total": len(rows),
        "verified": len(hashes),
        "rejected": len(reasons),
        "rejected_by_reason": dict(Counter(reasons.values())),
        "rejected_products": [{"product_id": key, "reason": reasons[key]} for key in sorted(reasons)],
        "duplicate_image_groups": sorted(duplicates),
        "verified_product_ids": sorted(hashes),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
