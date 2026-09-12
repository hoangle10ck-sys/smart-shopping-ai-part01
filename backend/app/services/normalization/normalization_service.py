"""Normalization and persistence orchestration."""

from dataclasses import (
    dataclass,
)

from sqlalchemy import (
    select,
)

from sqlalchemy.orm import (
    Session,
)

from app.models.product_offer import (
    ProductOffer,
    utc_now as offer_utc_now,
)

from app.schemas.normalization import (
    NormalizedProductCandidate,
)

from app.schemas.search import (
    RawProductCandidateData,
)

from app.services.dedup.product_deduplicator import (
    ProductDeduplicator,
)

from app.services.normalization.product_normalizer import (
    ProductNormalizer,
)


@dataclass(slots=True)
class PersistenceResult:
    """Result of persisting one normalized candidate."""

    product_id: int

    offer_id: int | None

    created_product: bool

    created_offer: bool


class NormalizationService:
    """Normalize and persist Product/ProductOffer records."""

    def __init__(
        self,
    ) -> None:

        self.normalizer = (
            ProductNormalizer()
        )

        self.deduplicator = (
            ProductDeduplicator()
        )


    def persist_candidate(
        self,
        *,
        db: Session,
        candidate: RawProductCandidateData,
        source_id: int | None = None,
        category: str | None = None,
        image_url: str | None = None,
    ) -> PersistenceResult | None:
        """Normalize and persist one raw candidate."""

        normalized = (
            self.normalizer.normalize(
                candidate,
            )
        )

        if (
            normalized
            is None
        ):
            return None


        # =====================================================
        # PRODUCT
        # =====================================================

        (
            product,
            created_product,
        ) = (
            self.deduplicator
            .get_or_create(
                db,
                normalized,
            )
        )


        # =====================================================
        # IMAGE
        #
        # IMPORTANT:
        # A newly resolved valid image may replace an old image.
        #
        # This fixes products that previously stored:
        # - search icon
        # - logo
        # - placeholder
        # =====================================================

        candidate_image = (
            image_url
            or candidate.image_url
        )

        if (
            candidate_image
            and candidate_image.strip()
        ):
            product.image_url = (
                candidate_image.strip()
            )


        # =====================================================
        # OFFER
        # =====================================================

        (
            offer,
            created_offer,
        ) = (
            self._upsert_offer(
                db=db,

                product_id=(
                    product.id
                ),

                candidate=(
                    normalized
                ),

                source_id=(
                    source_id
                ),
            )
        )


        db.flush()


        return (
            PersistenceResult(
                product_id=(
                    product.id
                ),

                offer_id=(
                    offer.id
                    if offer is not None
                    else None
                ),

                created_product=(
                    created_product
                ),

                created_offer=(
                    created_offer
                ),
            )
        )


    def _upsert_offer(
        self,
        *,
        db: Session,
        product_id: int,
        candidate: NormalizedProductCandidate,
        source_id: int | None,
    ) -> tuple[
        ProductOffer | None,
        bool,
    ]:
        """Create or update merchant-specific offer."""

        offer: (
            ProductOffer
            | None
        ) = None


        if (
            candidate.product_url
        ):
            offer = (
                db.scalar(
                    select(
                        ProductOffer
                    ).where(
                        ProductOffer.product_id
                        == product_id,

                        ProductOffer.product_url
                        == candidate.product_url,
                    )
                )
            )


        elif (
            source_id
            is not None
        ):
            offer = (
                db.scalar(
                    select(
                        ProductOffer
                    ).where(
                        ProductOffer.product_id
                        == product_id,

                        ProductOffer.source_id
                        == source_id,
                    )
                )
            )


        elif (
            candidate.source_domain
        ):
            offer = (
                db.scalar(
                    select(
                        ProductOffer
                    ).where(
                        ProductOffer.product_id
                        == product_id,

                        ProductOffer.merchant
                        == candidate.source_domain,
                    )
                )
            )


        if (
            offer
            is not None
        ):
            self._update_offer(
                offer=offer,
                candidate=candidate,
                source_id=source_id,
            )

            return (
                offer,
                False,
            )


        has_offer_evidence = any(
            [
                candidate.product_url,

                candidate.source_domain,

                source_id
                is not None,

                candidate.price
                is not None,

                candidate.availability,
            ]
        )


        if (
            not has_offer_evidence
        ):
            return (
                None,
                False,
            )


        offer = (
            ProductOffer(
                product_id=(
                    product_id
                ),

                merchant=(
                    candidate.source_domain
                ),

                price=(
                    candidate.price
                ),

                currency=(
                    candidate.currency
                ),

                availability=(
                    candidate.availability
                ),

                source_id=(
                    source_id
                ),

                product_url=(
                    candidate.product_url
                ),
            )
        )


        db.add(
            offer
        )

        db.flush()

        return (
            offer,
            True,
        )


    def _update_offer(
        self,
        *,
        offer: ProductOffer,
        candidate: NormalizedProductCandidate,
        source_id: int | None,
    ) -> None:
        """Update offer using available evidence."""

        if (
            candidate.source_domain
        ):
            offer.merchant = (
                candidate.source_domain
            )


        if (
            candidate.price
            is not None
        ):
            offer.price = (
                candidate.price
            )


        if (
            candidate.currency
        ):
            offer.currency = (
                candidate.currency
            )


        if (
            candidate.availability
        ):
            offer.availability = (
                candidate.availability
            )


        if (
            source_id
            is not None
        ):
            offer.source_id = (
                source_id
            )


        if (
            candidate.product_url
        ):
            offer.product_url = (
                candidate.product_url
            )


        offer.last_checked_at = (
            offer_utc_now()
        )
