"""Offline-only verified-image stand-in for synthetic integration URLs."""

from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit

import pytest


@pytest.fixture(autouse=True)
def synthetic_image_probe(monkeypatch):
    """Model an image probe only for reserved test domains; never reach the network."""
    from app.services.extraction.product_image_resolver import ProductImageResolver

    async def probe(self, url, *, allowed_hosts=None):
        host = (urlsplit(url).hostname or "").lower()
        if not (host.endswith(".example") or host.endswith(".test")):
            return {"accepted": False, "reason": "test_domain_not_allowlisted"}
        if allowed_hosts is not None and host not in allowed_hosts:
            return {"accepted": False, "reason": "unsafe_or_unapproved_host"}
        return {
            "accepted": True,
            "reason": "verified_raster_test_fixture",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "content_type": "image/jpeg",
            "content_sha256": sha256(url.encode("utf-8")).hexdigest(),
            "bytes_read": 128,
        }

    monkeypatch.setattr(ProductImageResolver, "verify_image", probe)

    from app.services.search.unified.catalog_source import DatabaseCatalogSource

    catalog_payload = DatabaseCatalogSource._catalog_payload

    def payload_with_test_image_evidence(product, offer):
        payload = catalog_payload(product, offer)
        image_url = product.image_url
        host = (urlsplit(image_url).hostname or "").lower() if image_url else ""
        if image_url and (host.endswith(".example") or host.endswith(".test")):
            image_probe = {
                "accepted": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "content_type": "image/jpeg",
                "content_sha256": sha256(image_url.encode("utf-8")).hexdigest(),
            }
            payload["page_validation"].update(
                source_observation_valid=True,
                image_url=image_url,
                image_source="synthetic_integration_fixture",
                image_probe=image_probe,
                evidence_url=offer.product_url,
            )
        return payload

    monkeypatch.setattr(DatabaseCatalogSource, "_catalog_payload", staticmethod(payload_with_test_image_evidence))
