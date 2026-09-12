"""Build scoring candidates from session-specific database evidence."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_offer import ProductOffer
from app.models.raw_product_candidate import (
    RawProductCandidate,
)
from app.models.source import Source
from app.schemas.ranking import ScoringCandidate
from app.schemas.requirement import RequirementData


@dataclass(slots=True)
class CandidateContext:
    """Candidate plus all database evidence used for recommendation."""

    candidate: ScoringCandidate

    product: Product

    offer: ProductOffer | None

    offers: list[ProductOffer]

    source_reliabilities: list[float]


class CandidateBuilder:
    """Build one scoring candidate per canonical product."""

    def build(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
    ) -> list[CandidateContext]:
        """Build candidates only from evidence seen in this session."""

        source_ids = list(
            db.scalars(
                select(
                    RawProductCandidate.source_id
                )
                .where(
                    RawProductCandidate.session_id
                    == session_id,
                    RawProductCandidate.source_id
                    .is_not(None),
                )
                .distinct()
            )
        )

        if not source_ids:
            return []

        offers = list(
            db.scalars(
                select(ProductOffer).where(
                    ProductOffer.source_id.in_(
                        source_ids
                    )
                )
            )
        )

        offers_by_product: dict[
            int,
            list[ProductOffer],
        ] = {}

        for offer in offers:
            offers_by_product.setdefault(
                offer.product_id,
                [],
            ).append(offer)

        contexts: list[
            CandidateContext
        ] = []

        for (
            product_id,
            product_offers,
        ) in offers_by_product.items():
            product = db.get(
                Product,
                product_id,
            )

            if product is None:
                continue

            best_offer = self._best_offer(
                product_offers
            )

            source_reliabilities: list[
                float
            ] = []

            best_source_reliability = 50.0

            for offer in product_offers:
                if offer.source_id is None:
                    continue

                source = db.get(
                    Source,
                    offer.source_id,
                )

                if source is None:
                    continue

                reliability = (
                    source.reliability_score
                    if source.reliability_score
                    is not None
                    else 50.0
                )

                source_reliabilities.append(
                    float(reliability)
                )

                if (
                    best_offer is not None
                    and offer.id
                    == best_offer.id
                ):
                    best_source_reliability = (
                        float(reliability)
                    )

            specifications = {
                str(key): str(value)
                for key, value
                in (
                    product.specifications
                    or {}
                ).items()
            }

            candidate = ScoringCandidate(
                product_id=product.id,
                name=(
                    product.name
                    or f"Product {product.id}"
                ),
                category=(
                    product.category
                    or requirement.category
                ),
                brand=product.brand,
                model=product.model,
                price=(
                    best_offer.price
                    if best_offer
                    is not None
                    else None
                ),
                currency=(
                    best_offer.currency
                    if best_offer
                    is not None
                    else requirement.currency
                ),
                rating=product.rating,
                review_count=(
                    product.review_count
                ),
                availability=(
                    best_offer.availability
                    if best_offer
                    is not None
                    else None
                ),
                source_reliability=(
                    best_source_reliability
                ),
                specifications=(
                    specifications
                ),
            )

            contexts.append(
                CandidateContext(
                    candidate=candidate,
                    product=product,
                    offer=best_offer,
                    offers=list(
                        product_offers
                    ),
                    source_reliabilities=(
                        source_reliabilities
                    ),
                )
            )

        contexts.sort(
            key=lambda item: (
                item.candidate.product_id
            )
        )

        return contexts

    def _best_offer(
        self,
        offers: list[ProductOffer],
    ) -> ProductOffer | None:
        """Choose deterministic best offer."""

        if not offers:
            return None

        def sort_key(
            offer: ProductOffer,
        ) -> tuple[
            int,
            int,
            int,
            int,
        ]:
            availability = (
                offer.availability
                or ""
            ).lower()

            unavailable = int(
                availability
                in {
                    "out_of_stock",
                    "out of stock",
                    "sold out",
                    "unavailable",
                    "het hang",
                }
            )

            missing_price = int(
                offer.price is None
            )

            price = (
                offer.price
                if offer.price
                is not None
                else 10**18
            )

            return (
                unavailable,
                missing_price,
                price,
                offer.id or 0,
            )

        return min(
            offers,
            key=sort_key,
        )