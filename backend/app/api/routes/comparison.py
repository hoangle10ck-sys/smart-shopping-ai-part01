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
from app.schemas.recommendation import RecommendationItem
from app.services.recommendation.recommendation_service import RecommendationService
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


def _serialize_product(item: RecommendationItem) -> dict[str, Any]:
    """Project a consistent recommendation view into the existing API shape."""
    explanation = item.explanation
    return {
        "product_id": item.product_id,
        "name": item.name,
        "category": item.category,
        "brand": item.brand,
        "model": item.model,
        "image_url": item.image_url,
        "rating": item.rating,
        "review_count": item.review_count,
        "specifications": dict(item.specifications),
        "pros": list(explanation.why_fit) if explanation else [],
        "cons": list(explanation.tradeoffs) if explanation else [],
        "ai_score": item.score.final_score,
        "confidence": item.confidence,
        "recommendation_rank": item.rank,
        "best_offer": {
            "merchant": item.merchant,
            "price": item.price,
            "currency": item.currency,
            "availability": item.availability,
            "product_url": item.product_url,
        } if item.price is not None else None,
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

    # Snapshot-backed sessions never join historical scores to mutable offers.
    # Legacy sessions use the existing complete, read-only recomputation path.
    try:
        view = RecommendationService().load(db=db, session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    items_by_id = {item.product_id: item for item in view.recommendations}
    unavailable = [product_id for product_id in payload.product_ids if product_id not in items_by_id]
    if unavailable:
        raise HTTPException(status_code=409, detail={
            "message": "Selected products are not available in the consistent session view.",
            "product_ids": unavailable,
        })
    comparison_products = [_serialize_product(items_by_id[product_id]) for product_id in payload.product_ids]

    result = _build_result(
        products=comparison_products,
    )

    comparison = ComparisonSession(
        session_id=payload.session_id,
        product_ids=payload.product_ids,
        result=result,
    )

    result["data_semantics"] = view.data_semantics
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
