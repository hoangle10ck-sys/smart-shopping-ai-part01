"""Product comparison API endpoints."""

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.comparison import (
    ComparisonSession,
)
from app.models.product import Product
from app.models.recommendation import (
    Recommendation,
)
from app.models.search_session import (
    SearchSession,
)
from app.schemas.comparison import (
    ComparisonCreateRequest,
    ComparisonResponse,
)


router = APIRouter(
    prefix="/api/comparisons",
    tags=["Comparison"],
)


def _to_float(
    value: object,
) -> float | None:
    """Safely convert numeric value to float."""

    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _best_offer(
    product: Product,
) -> dict[str, Any] | None:
    """Return the cheapest valid offer of a product."""

    valid_offers: list[
        tuple[float, object]
    ] = []

    for offer in product.offers:
        price = _to_float(
            getattr(
                offer,
                "price",
                None,
            )
        )

        if price is None:
            continue

        if price < 0:
            continue

        valid_offers.append(
            (
                price,
                offer,
            )
        )

    if not valid_offers:
        return None

    price, offer = min(
        valid_offers,
        key=lambda item: item[0],
    )

    return {
        "merchant": getattr(
            offer,
            "merchant",
            None,
        ),
        "price": price,
        "currency": (
            getattr(
                offer,
                "currency",
                None,
            )
            or "VND"
        ),
        "availability": getattr(
            offer,
            "availability",
            None,
        ),
        "product_url": getattr(
            offer,
            "product_url",
            None,
        ),
    }


def _serialize_product(
    *,
    product: Product,
    recommendation: Recommendation,
) -> dict[str, Any]:
    """Convert product and recommendation into comparison data."""

    return {
        "product_id": product.id,
        "name": product.name,
        "category": product.category,
        "brand": product.brand,
        "model": product.model,
        "image_url": product.image_url,
        "rating": product.rating,
        "review_count": product.review_count,
        "specifications": (
            product.specifications
            or {}
        ),
        "pros": (
            product.pros
            or []
        ),
        "cons": (
            product.cons
            or []
        ),
        "ai_score": _to_float(
            recommendation.final_score
        ),
        "confidence": _to_float(
            recommendation.confidence
        ),
        "recommendation_rank": (
            recommendation.rank
        ),
        "best_offer": (
            _best_offer(product)
        ),
    }


def _winner_key(
    item: dict[str, Any],
) -> tuple[
    float,
    float,
    int,
]:
    """Build deterministic winner sort key."""

    score = (
        item.get("ai_score")
        or 0.0
    )

    rating = (
        item.get("rating")
        or 0.0
    )

    reviews = (
        item.get("review_count")
        or 0
    )

    return (
        float(score),
        float(rating),
        int(reviews),
    )


def _build_result(
    *,
    products: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    """Build deterministic AI comparison result."""

    winner = max(
        products,
        key=_winner_key,
    )

    winner_name = (
        winner.get("name")
        or (
            f"Sản phẩm "
            f"#{winner['product_id']}"
        )
    )

    summary = (
        f"{winner_name} được đề xuất "
        "cao nhất trong các sản phẩm "
        "đang so sánh vì có AI score "
        "tốt nhất. Rating và số lượng "
        "đánh giá được dùng làm tiêu chí "
        "phụ khi cần phân hạng."
    )

    return {
        "winner_product_id": (
            winner["product_id"]
        ),
        "summary": summary,
        "criteria": [
            "AI score",
            "Confidence",
            "Price",
            "Rating",
            "Review count",
            "Specifications",
            "Pros",
            "Cons",
        ],
        "products": products,
    }


@router.post(
    "",
    response_model=ComparisonResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_comparison(
    payload: ComparisonCreateRequest,
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    """Compare two or three products."""

    search_session = db.get(
        SearchSession,
        payload.session_id,
    )

    if search_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Không tìm thấy search session."
            ),
        )

    product_models = list(
        db.scalars(
            select(Product)
            .where(
                Product.id.in_(
                    payload.product_ids
                )
            )
        )
    )

    products_by_id = {
        product.id: product
        for product in product_models
    }

    missing_product_ids = [
        product_id
        for product_id
        in payload.product_ids
        if product_id
        not in products_by_id
    ]

    if missing_product_ids:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail={
                "message": (
                    "Không tìm thấy "
                    "một số sản phẩm."
                ),
                "product_ids": (
                    missing_product_ids
                ),
            },
        )

    recommendation_models = list(
        db.scalars(
            select(Recommendation)
            .where(
                Recommendation.session_id
                == payload.session_id,
                Recommendation.product_id.in_(
                    payload.product_ids
                ),
            )
        )
    )

    recommendations_by_product = {
        item.product_id: item
        for item
        in recommendation_models
    }

    invalid_product_ids = [
        product_id
        for product_id
        in payload.product_ids
        if product_id
        not in recommendations_by_product
    ]

    if invalid_product_ids:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail={
                "message": (
                    "Sản phẩm chưa thuộc "
                    "kết quả recommendation "
                    "của search session này."
                ),
                "product_ids": (
                    invalid_product_ids
                ),
            },
        )

    comparison_products: list[
        dict[str, Any]
    ] = []

    for product_id in payload.product_ids:
        comparison_products.append(
            _serialize_product(
                product=(
                    products_by_id[
                        product_id
                    ]
                ),
                recommendation=(
                    recommendations_by_product[
                        product_id
                    ]
                ),
            )
        )

    result = _build_result(
        products=comparison_products,
    )

    comparison = ComparisonSession(
        session_id=payload.session_id,
        product_ids=payload.product_ids,
        result=result,
    )

    db.add(comparison)
    db.commit()
    db.refresh(comparison)

    return ComparisonResponse.model_validate(
        comparison
    )


@router.get(
    "/{comparison_id}",
    response_model=ComparisonResponse,
)
def get_comparison(
    comparison_id: int,
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    """Return a persisted comparison."""

    comparison = db.get(
        ComparisonSession,
        comparison_id,
    )

    if comparison is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Không tìm thấy comparison."
            ),
        )

    return ComparisonResponse.model_validate(
        comparison
    )