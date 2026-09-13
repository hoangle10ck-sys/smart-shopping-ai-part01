"""Attribute fields only to matching raw observations from this search session."""

from datetime import timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.raw_product_candidate import RawProductCandidate
from app.models.source import Source
from app.schemas.evidence import FieldEvidence
from app.schemas.search import RawProductCandidateData
from app.services.normalization.product_normalizer import ProductNormalizer
from app.services.recommendation.candidate_builder import CandidateContext


def build_field_evidence(db: Session, session_id: str, context: CandidateContext) -> list[FieldEvidence]:
    """Do not assign consolidated product fields to the cheapest offer by inference.

    A source must contain the same product name AND the same normalized value.
    Missing/older/untraceable observations stay absent. This conservative mapping
    may omit aliases; it must not invent attribution. Called only when generating
    a view, never when loading a historical snapshot.
    """
    result: list[FieldEvidence] = []
    seen: set[tuple[str, str]] = set()
    candidate, offer = context.candidate, context.offer
    rows = db.execute(select(RawProductCandidate, Source).join(
        Source, Source.id == RawProductCandidate.source_id
    ).where(RawProductCandidate.session_id == session_id).order_by(RawProductCandidate.id))
    normalizer = ProductNormalizer()
    for raw, source in rows:
        try:
            observed = normalizer.normalize(RawProductCandidateData.model_validate(raw.payload))
        except ValidationError:
            continue
        if observed is None or observed.normalized_name != context.product.normalized_name:
            continue
        associated = next((item for item in context.offers
                           if item.source_id == source.id and item.product_url == observed.product_url), None)
        if associated is None:
            continue
        fields: dict[str, str | int | float] = {}
        if (offer is not None and offer.source_id == source.id
                and observed.product_url == offer.product_url
                and observed.currency == candidate.currency
                and observed.price is not None and observed.price == candidate.price):
            fields["price"] = observed.price
        for name in ("rating", "review_count"):
            value = getattr(observed, name)
            if value is not None and value == getattr(candidate, name):
                fields[name] = value
        for name, value in observed.specifications.items():
            if value == candidate.specifications.get(name):
                fields[f"specifications.{name}"] = value
        for field, value in fields.items():
            if (field, source.url) in seen:
                continue
            seen.add((field, source.url))
            result.append(FieldEvidence(
                field=field, value=value, source=source.title, domain=source.domain,
                # Merchant is only known for the actual associated offer.
                merchant=associated.merchant,
                url=source.url,
                retrieved_at=(raw.created_at.replace(tzinfo=timezone.utc)
                              if raw.created_at.tzinfo is None else raw.created_at),
                reliability=source.reliability_score,
            ))
    return result
