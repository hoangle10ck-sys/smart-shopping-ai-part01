"""Build product-image evidence from an already validated source observation."""

from app.schemas.product_image import ProductImageEvidence
from app.services.product_images.eligibility import has_verified_image


def page_image_evidence(
    *,
    proof: dict | None,
    image_url: str | None,
    product_url: str | None,
    identifier_value: str | None,
    model: str | None,
) -> ProductImageEvidence | None:
    """Require same-page identity proof and a successful full-image probe."""

    if not isinstance(proof, dict) or not image_url:
        return None
    if proof.get("image_url") != image_url:
        return None
    probe = proof.get("image_probe")
    if not isinstance(probe, dict) or not probe.get("accepted"):
        return None
    source_observation_valid = proof.get("source_observation_valid") is True
    product_page_valid = proof.get("product_page_valid") is True
    verification_level = proof.get("verification_level")
    if not (
        source_observation_valid
        or (product_page_valid and verification_level in {"VERIFIED_CONTENT", "VERIFIED_PUBLIC_API"})
    ):
        return None

    identifier = (identifier_value or "").strip()
    if identifier:
        identifier_type = "SOURCE_PRODUCT_ID"
    else:
        identifier = (model or "").strip()
        identifier_type = "MODEL"
    if not identifier:
        # A same-page Product record whose own image was probed is a valid
        # identity anchor even when the manufacturer omits a separate model.
        identifier = str(proof.get("name") or "").strip()
        identifier_type = "PRODUCT_NAME"
    if not identifier:
        return None
    source_url = proof.get("evidence_url") or product_url
    if not isinstance(source_url, str) or not source_url:
        return None

    source_type = "VERIFIED_PUBLIC_API" if verification_level == "VERIFIED_PUBLIC_API" else "VERIFIED_PRODUCT_PAGE"
    verification_method = (
        "PUBLIC_API_IDENTIFIER_MATCH"
        if source_type == "VERIFIED_PUBLIC_API"
        else "IDENTIFIER_MATCHED_PAGE"
    )
    try:
        evidence = ProductImageEvidence(
            status="VERIFIED",
            image_url=image_url,
            source_type=source_type,
            source_url=source_url,
            identifier_type=identifier_type,
            identifier_value=identifier,
            verification_method=verification_method,
            checked_at=probe["checked_at"],
            content_type=probe["content_type"],
            content_sha256=probe["content_sha256"],
            license=proof.get("image_license"),
            license_url=proof.get("image_license_url"),
        )
        return evidence if has_verified_image(image_url, evidence) else None
    except (KeyError, TypeError, ValueError):
        return None
