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
from app.models.product import Product
from app.models.product_offer import (
    ProductOffer,
)
from app.schemas.product import (
    ProductDetailResponse,
    ProductOfferItem,
)


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

        offers.append(
            ProductOfferItem(
                id=offer.id,
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

    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        category=product.category,
        brand=product.brand,
        model=product.model,
        normalized_name=(
            product.normalized_name
        ),
        image_url=product.image_url,
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