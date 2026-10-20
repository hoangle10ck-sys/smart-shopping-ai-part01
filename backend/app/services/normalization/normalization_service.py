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

        if candidate.page_validation is not None and not (
            candidate.page_validation.get("product_page_valid")
            or candidate.page_validation.get("source_observation_valid")
        ):
            db.flush()
            return PersistenceResult(product.id, None, created_product, False)

        if normalized.platform and normalized.platform != "unknown" and (
            normalized.external_sku_id or normalized.variant_attributes
        ):
            from datetime import datetime, timezone
            from app.schemas.collector import OfferObservation, PriceRange, VariantIdentity
            from app.services.collectors.persistence import persist_offer_observation
            price_range = (PriceRange(minimum=normalized.price_min, maximum=normalized.price_max)
                           if normalized.price_min is not None and normalized.price_max is not None else None)
            result = persist_offer_observation(db, product_id=product.id, source_id=source_id,
                observation=OfferObservation(identity=VariantIdentity(platform=normalized.platform,
                    external_product_id=normalized.external_product_id,
                    external_shop_id=normalized.external_shop_id,
                    external_sku_id=normalized.external_sku_id,
                    attributes=normalized.variant_attributes, condition=normalized.condition),
                    merchant=candidate.merchant, listed_price=normalized.listed_price,
                    sale_price=normalized.sale_price if normalized.sale_price is not None else normalized.price,
                    listed_price_minor_units=normalized.listed_price_minor_units,
                    sale_price_minor_units=normalized.sale_price_minor_units,
                    currency_minor_unit=normalized.currency_minor_unit,
                    price_range=price_range, currency=normalized.currency,
                    shipping_fee=normalized.shipping_fee, voucher=normalized.voucher,
                    warranty=normalized.warranty,
                    availability=normalized.availability, product_url=normalized.product_url or candidate.evidence_url or "",
                    observed_at=normalized.observed_at or datetime.now(timezone.utc)))
            return PersistenceResult(product.id, result.offer.id, created_product, result.offer_created)

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


        if offer is not None and candidate.merchant:
            offer.merchant = candidate.merchant
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
                listed_price=candidate.listed_price,
                sale_price=candidate.sale_price,
                listed_price_minor_units=candidate.listed_price_minor_units,
                sale_price_minor_units=candidate.sale_price_minor_units,
                currency_minor_unit=candidate.currency_minor_unit,

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
        offer.listed_price = candidate.listed_price
        offer.sale_price = candidate.sale_price
        offer.listed_price_minor_units = candidate.listed_price_minor_units
        offer.sale_price_minor_units = candidate.sale_price_minor_units
        offer.currency_minor_unit = candidate.currency_minor_unit


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
