"""Product detail API endpoints."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.core.database import get_db
from app.api.guest_owner import get_existing_guest_owner, require_owned_session
from app.models.product import Product
from app.models.user import User
from app.services.research.recommendation import catalog_metadata
from app.services.recommendation.candidate_builder import offer_observation
from app.services.recommendation.recommendation_service import RecommendationService
from app.models.product_offer import (
    ProductOffer,
)
from app.schemas.product import (
    ProductDetailResponse,
    ProductOfferItem,
)
from app.services.product_images.page_evidence import page_image_evidence


router = APIRouter(
    prefix="/api/products",
    tags=["Products"],
)


def _offer_sort_key(
    offer: ProductOffer,
) -> tuple[int, int, int]:
    """Sort valid priced offers before missing-price offers."""

    missing_price = int(
        offer.price is None
    )

    price = (
        offer.price
        if offer.price is not None
        else 10**18
    )

    return (
        missing_price,
        price,
        offer.id or 0,
    )


@router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    session_id: str | None = None,
    owner: User | None = Depends(get_existing_guest_owner),
) -> ProductDetailResponse:
    """Return complete product information."""

    product = db.scalar(
        select(Product)
        .options(
            selectinload(
                Product.offers
            ).selectinload(
                ProductOffer.source
            )
        )
        .where(
            Product.id == product_id
        )
    )

    if product is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Không tìm thấy sản phẩm.",
        )

    offers: list[
        ProductOfferItem
    ] = []

    for offer in sorted(
        product.offers,
        key=_offer_sort_key,
    ):
        source = offer.source
        proof = offer_observation(db, offer, product)
        image_url = proof.get("image_url") if proof else None
        image_evidence = page_image_evidence(
            proof=proof,
            image_url=image_url,
            product_url=offer.product_url,
            identifier_value=offer.external_product_id,
            model=product.model,
        )
        if image_evidence is None:
            continue

        offers.append(
            ProductOfferItem(
                id=offer.id,
                variant_id=offer.variant_id, platform=offer.platform,
                external_product_id=offer.external_product_id,
                external_shop_id=offer.external_shop_id, external_sku_id=offer.external_sku_id,
                listed_price=offer.listed_price, sale_price=offer.sale_price,
                price_min=offer.price_min, price_max=offer.price_max,
                shipping_fee=offer.shipping_fee, freshness_status=offer.freshness_status,
                warranty=offer.warranty,
                last_verified_at=offer.last_verified_at,
                image_url=str(image_evidence.image_url),
                image_evidence=image_evidence,
                image_source=proof.get('image_source') if proof else None,
                product_page_valid=proof.get('product_page_valid') if proof else None,
                source_observation_valid=proof.get('source_observation_valid') if proof else None,
                price_type=proof.get('price_type') if proof else None,
                variant=proof.get('variant') if proof else None,
                verification_level=proof.get('verification_level') if proof else None,
                product_page_confidence=proof.get('product_page_confidence') if proof else None,
                evidence_url=proof.get('evidence_url') if proof else (source.url if source else None),
                merchant=offer.merchant,
                price=offer.price,
                currency=(
                    offer.currency
                    or "VND"
                ),
                availability=(
                    offer.availability
                ),
                source_id=offer.source_id,
                source_domain=(
                    source.domain
                    if source is not None
                    else None
                ),
                source_title=(
                    source.title
                    if source is not None
                    else None
                ),
                source_reliability_score=(
                    source.reliability_score
                    if source is not None
                    else None
                ),
                product_url=(
                    offer.product_url
                ),
                last_checked_at=(
                    offer.last_checked_at
                ),
            )
        )

    recommendation = None
    if session_id:
        if owner is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy search session.")
        require_owned_session(db, session_id, owner)
        try:
            view = RecommendationService().load(db=db, session_id=session_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        recommendation = next((item for item in view.recommendations if item.product_id == product_id), None)
        if recommendation is None:
            raise HTTPException(status_code=404, detail="Product not recommended in this session.")
    image_evidence = recommendation.image_evidence if recommendation is not None else None
    image_url = recommendation.image_url if recommendation is not None else None
    if image_evidence is None:
        eligible_offer = next((offer for offer in offers if offer.image_evidence is not None), None)
        if eligible_offer is not None:
            image_evidence = eligible_offer.image_evidence
            image_url = eligible_offer.image_url
    if image_evidence is None or image_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product has no currently verified image evidence.",
        )
    return ProductDetailResponse(
        **catalog_metadata(db, product.id),
        recommendation=recommendation,
        recommendation_session_id=session_id,
        id=product.id,
        name=product.name,
        category=product.category,
        brand=product.brand,
        model=product.model,
        normalized_name=(
            product.normalized_name
        ),
        image_url=image_url,
        image_evidence=image_evidence,
        rating=product.rating,
        review_count=(
            product.review_count
        ),
        specifications=(
            product.specifications
            or {}
        ),
        pros=product.pros or [],
        cons=product.cons or [],
        offers=offers,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )
