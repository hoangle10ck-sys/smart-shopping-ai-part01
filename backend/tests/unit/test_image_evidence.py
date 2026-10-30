from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.product_image import ProductImageEvidence
from app.services.product_images.eligibility import apply_image_eligibility_to_items, has_verified_image
from app.services.product_images.page_evidence import page_image_evidence
from types import SimpleNamespace


def valid_evidence(**overrides):
    values = {
        "status": "VERIFIED",
        "image_url": "https://images.openproductsfacts.org/images/products/123/front.jpg",
        "source_type": "RESEARCH_DATASET",
        "source_url": "https://world.openproductsfacts.org/product/123",
        "identifier_type": "GTIN",
        "identifier_value": "123",
        "verification_method": "SAME_SOURCE_RECORD",
        "checked_at": datetime.now(timezone.utc),
        "content_type": "image/jpeg",
        "content_sha256": "a" * 64,
        "license": "CC BY-SA 4.0",
    }
    values.update(overrides)
    return ProductImageEvidence.model_validate(values)


def test_only_a_verified_image_bound_to_the_same_item_is_eligible():
    evidence = valid_evidence()
    assert has_verified_image(evidence.image_url, evidence)
    assert not has_verified_image(None, evidence)
    assert not has_verified_image("https://images.example/other.jpg", evidence)
    assert not has_verified_image(evidence.image_url, None)


def test_stale_and_future_image_probes_are_not_eligible():
    now = datetime.now(timezone.utc)
    image_url = "https://images.openproductsfacts.org/images/products/123/front.jpg"
    assert not has_verified_image(image_url, valid_evidence(checked_at=now - timedelta(hours=25)))
    assert not has_verified_image(image_url, valid_evidence(checked_at=now + timedelta(minutes=1)))


def test_shared_image_bytes_across_distinct_products_are_rejected_as_ambiguous():
    evidence = valid_evidence()
    items = [
        SimpleNamespace(product_id=10, image_url=str(evidence.image_url), image_evidence=evidence),
        SimpleNamespace(product_id=11, image_url=str(evidence.image_url), image_evidence=evidence),
    ]
    accepted, rejected = apply_image_eligibility_to_items(items, [])
    assert accepted == []
    assert rejected == {10: "IMAGE_DUPLICATE_IDENTITY_CONFLICT", 11: "IMAGE_DUPLICATE_IDENTITY_CONFLICT"}


def test_same_page_product_name_can_anchor_an_image_when_model_is_missing():
    image_url = "https://shop.example/images/product.jpg"
    evidence = page_image_evidence(
        proof={
            "product_page_valid": True,
            "verification_level": "VERIFIED_CONTENT",
            "name": "Acme Model X",
            "evidence_url": "https://shop.example/products/acme-model-x",
            "image_url": image_url,
            "image_probe": {
                "accepted": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "content_type": "image/jpeg",
                "content_sha256": "b" * 64,
            },
        },
        image_url=image_url,
        product_url="https://shop.example/products/acme-model-x",
        identifier_value=None,
        model=None,
    )
    assert evidence is not None
    assert evidence.identifier_type == "PRODUCT_NAME"
    assert evidence.identifier_value == "Acme Model X"


@pytest.mark.parametrize(
    "overrides",
    [
        {"identifier_value": "  "},
        {"content_type": "text/html"},
        {"content_sha256": "not-a-hash"},
        {"source_url": "javascript:alert(1)"},
        {"status": "UNVERIFIED"},
    ],
)
def test_evidence_rejects_missing_or_unsafe_verification_fields(overrides):
    with pytest.raises(ValidationError):
        valid_evidence(**overrides)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,accepted,reason", [
    ("success", True, None),
    ("timeout", False, "http_transport_error"),
    ("http_error", False, "http_503"),
    ("empty", False, "invalid_or_tiny_raster"),
])
async def test_image_probe_success_timeout_http_error_and_empty(monkeypatch, mode, accepted, reason):
    import httpx
    from app.services.extraction import product_image_resolver as module

    original = httpx.AsyncClient
    def transport(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("offline synthetic timeout", request=request)
        if mode == "http_error":
            return httpx.Response(503, request=request)
        if mode == "empty":
            return httpx.Response(200, request=request, headers={"content-type": "image/jpeg"}, content=b"")
        return httpx.Response(
            200, request=request, headers={"content-type": "image/jpeg"},
            content=b"\xff\xd8\xff" + b"x" * 100 + b"\xff\xd9",
        )

    async def public_url(url):
        return True

    monkeypatch.setattr(module, "_safe_public_url", public_url)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs))
    result = await module.ProductImageResolver().verify_image(
        "https://images.example/product.jpg", allowed_hosts={"images.example"}
    )
    assert result["accepted"] is accepted
    if reason:
        assert result["reason"] == reason
    else:
        assert len(result["content_sha256"]) == 64
