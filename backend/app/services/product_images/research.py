"""Verify image assets attached to trusted research source records."""

from __future__ import annotations

import asyncio
from sqlalchemy import func, select
from urllib.parse import urlsplit

from app.models.product import Product
from app.schemas.product_image import ProductImageEvidence
from app.schemas.recommendation import RecommendationItem
from app.services.extraction.product_image_resolver import ProductImageResolver


RESEARCH_IMAGE_HOSTS = {
    "Amazon-Berkeley-Objects": "amazon-berkeley-objects.s3.amazonaws.com",
    "OpenFoodFacts": "images.openfoodfacts.org",
    "OpenProductsFacts": "images.openproductsfacts.org",
}


def _source_evidence(item: RecommendationItem) -> tuple[dict | None, str | None]:
    provenance = item.research_provenance or {}
    dataset_id = provenance.get("dataset_id")
    host = RESEARCH_IMAGE_HOSTS.get(dataset_id)
    identifier = provenance.get("external_product_id")
    image_license = provenance.get("image_license") or provenance.get("license")
    source_url = provenance.get("source_product_url") or provenance.get("dataset_url") or provenance.get("source_url")
    if not item.image_url:
        return None, "IMAGE_MISSING"
    if not host or not isinstance(identifier, str) or not identifier.strip():
        return None, "IMAGE_IDENTITY_UNVERIFIED"
    if not image_license or not isinstance(source_url, str):
        return None, "IMAGE_SOURCE_UNVERIFIED"
    try:
        parsed = urlsplit(item.image_url)
        source_host = urlsplit(source_url).hostname
    except ValueError:
        return None, "IMAGE_SOURCE_UNVERIFIED"
    if parsed.scheme != "https" or parsed.hostname != host or not source_host:
        return None, "IMAGE_SOURCE_UNVERIFIED"

    identifier_label = provenance.get("identifier_label")
    if dataset_id == "OpenFoodFacts" or dataset_id == "OpenProductsFacts":
        if identifier_label != "barcode" or not identifier.isdecimal():
            return None, "IMAGE_IDENTITY_UNVERIFIED"
        identifier_type = "GTIN"
    elif dataset_id == "Amazon-Berkeley-Objects":
        if identifier_label not in {None, "item_id"}:
            return None, "IMAGE_IDENTITY_UNVERIFIED"
        identifier_type = "DATASET_RECORD"
    else:
        return None, "IMAGE_IDENTITY_UNVERIFIED"

    return {
        "host": host,
        "source_type": "RESEARCH_DATASET",
        "source_url": source_url,
        "identifier_type": identifier_type,
        "identifier_value": identifier.strip(),
        "verification_method": "SAME_SOURCE_RECORD",
        "license": image_license,
        "license_url": provenance.get("image_license_url") or provenance.get("license_url"),
    }, None


async def verify_research_image(
    item: RecommendationItem,
    resolver: ProductImageResolver,
) -> str | None:
    """Attach evidence only after the source record and complete image bytes validate."""

    source, reason = _source_evidence(item)
    if reason:
        item.image_url = None
        item.image_evidence = None
        return reason

    result = await resolver.verify_image(
        item.image_url,
        allowed_hosts={source["host"]},
    )
    if not result.get("accepted"):
        probe_reason = str(result.get("reason", ""))
        if probe_reason in {"non_raster_mime", "invalid_or_tiny_raster", "image_too_large"}:
            reason = "IMAGE_INVALID_CONTENT"
        elif probe_reason.startswith("http_") or probe_reason in {
            "http_transport_error", "redirect_limit", "redirect_outside_approved_host",
        }:
            reason = "IMAGE_UNAVAILABLE"
        else:
            reason = "IMAGE_SOURCE_UNVERIFIED"
        item.image_url = None
        item.image_evidence = None
        return reason

    try:
        item.image_evidence = ProductImageEvidence(
            status="VERIFIED",
            image_url=item.image_url,
            source_type=source["source_type"],
            source_url=source["source_url"],
            identifier_type=source["identifier_type"],
            identifier_value=source["identifier_value"],
            verification_method=source["verification_method"],
            checked_at=result["checked_at"],
            content_type=result["content_type"],
            content_sha256=result["content_sha256"],
            license=source["license"],
            license_url=source["license_url"],
        )
    except (KeyError, TypeError, ValueError):
        item.image_url = None
        item.image_evidence = None
        return "IMAGE_EVIDENCE_INCOMPLETE"
    return None


async def verify_research_images(
    items: list[RecommendationItem],
    *,
    db=None,
    concurrency: int = 4,
) -> dict[int, str]:
    """Verify returned research items with bounded concurrency; return rejection reasons."""

    resolver = ProductImageResolver(concurrency=concurrency)
    semaphore = asyncio.Semaphore(max(1, min(concurrency, 8)))
    rejected: dict[int, str] = {}
    duplicate_urls: set[str] = set()
    if db is not None:
        urls = {str(item.image_url) for item in items if item.image_url}
        if urls:
            duplicate_urls = set(db.scalars(
                select(Product.image_url)
                .where(Product.image_url.in_(urls))
                .group_by(Product.image_url)
                .having(func.count(Product.id) > 1)
            ))
            rejected.update({
                item.product_id: "IMAGE_DUPLICATE_IDENTITY_CONFLICT"
                for item in items if item.image_url and str(item.image_url) in duplicate_urls
            })

    async def verify(item: RecommendationItem) -> tuple[int, str | None]:
        async with semaphore:
            return item.product_id, await verify_research_image(item, resolver)

    async with resolver.session():
        results = await asyncio.gather(*(
            verify(item) for item in items
            if not item.image_url or str(item.image_url) not in duplicate_urls
        ))
    rejected.update({product_id: reason for product_id, reason in results if reason is not None})
    return rejected
