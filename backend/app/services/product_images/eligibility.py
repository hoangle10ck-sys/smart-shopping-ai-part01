"""Shared eligibility rule for product images returned by API routes."""

from datetime import datetime, timedelta, timezone

from app.schemas.product_image import ProductImageEvidence

IMAGE_EVIDENCE_MAX_AGE = timedelta(hours=24)


def has_verified_image(
    image_url: str | None,
    evidence: ProductImageEvidence | dict | None,
) -> bool:
    """Require a matching URL and complete source, identity, and byte evidence."""

    if not image_url or evidence is None:
        return False
    try:
        parsed = (
            evidence
            if isinstance(evidence, ProductImageEvidence)
            else ProductImageEvidence.model_validate(evidence)
        )
    except (TypeError, ValueError):
        return False
    now = datetime.now(timezone.utc)
    checked_at = parsed.checked_at.astimezone(timezone.utc)
    return (
        parsed.status == "VERIFIED"
        and str(parsed.image_url) == str(image_url)
        and checked_at <= now
        and now - checked_at <= IMAGE_EVIDENCE_MAX_AGE
    )


def apply_image_eligibility(result, rejection_reasons: dict[int, str] | None = None) -> dict[int, str]:
    """Remove unverified items and mark their existing filter decisions accurately."""

    previous_recommendation_count = len(result.recommendations)
    previous_filtered_count = result.total_filtered
    rejection_reasons = rejection_reasons or {}
    accepted, rejected = apply_image_eligibility_to_items(
        result.recommendations, result.filter_decisions, rejection_reasons
    )
    result.recommendations = accepted
    removed = previous_recommendation_count - len(accepted)
    result.total_filtered = max(len(accepted), previous_filtered_count - removed)
    return rejected


def apply_image_eligibility_to_items(
    recommendations: list,
    decisions_list: list,
    rejection_reasons: dict[int, str] | None = None,
) -> tuple[list, dict[int, str]]:
    rejection_reasons = rejection_reasons or {}
    hashes: dict[str, set[int]] = {}
    for item in recommendations:
        if not has_verified_image(item.image_url, item.image_evidence):
            continue
        digest = item.image_evidence.content_sha256
        hashes.setdefault(digest, set()).add(item.product_id)
    duplicate_products = {
        product_id
        for product_ids in hashes.values()
        if len(product_ids) > 1
        for product_id in product_ids
    }
    accepted = []
    rejected: dict[int, str] = {}
    decisions = {decision.product_id: decision for decision in decisions_list}
    for item in recommendations:
        if has_verified_image(item.image_url, item.image_evidence) and item.product_id not in duplicate_products:
            accepted.append(item)
            continue
        reason = (
            "IMAGE_DUPLICATE_IDENTITY_CONFLICT"
            if item.product_id in duplicate_products
            else rejection_reasons.get(item.product_id, "IMAGE_EVIDENCE_INCOMPLETE")
        )
        rejected[item.product_id] = reason
        decision = decisions.get(item.product_id)
        if decision is not None:
            decision.accepted = False
            decision.rejection_stage = "image_evidence"
            if reason not in decision.reasons:
                decision.reasons = [*decision.reasons, reason]
        item.image_url = None
        item.image_evidence = None
    return accepted, rejected
