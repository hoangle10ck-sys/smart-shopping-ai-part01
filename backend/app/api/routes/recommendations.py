"""Recommendation read API endpoints."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.recommendation import (
    Recommendation,
)
from app.models.search_session import (
    SearchSession,
)
from app.schemas.recommendation_api import (
    RecommendationDetailResponse,
    RecommendationSessionResponse,
)
from app.services.recommendation.recommendation_service import (
    RecommendationService,
)


router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"],
)


@router.get(
    "/session/{session_id}",
    response_model=(
        RecommendationSessionResponse
    ),
)
def get_session_recommendations(
    session_id: str,
    db: Session = Depends(get_db),
) -> RecommendationSessionResponse:
    """Return recommendations for one search session."""

    search_session = db.get(
        SearchSession,
        session_id,
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

    try:
        result = (
            RecommendationService().load(
                db=db,
                session_id=session_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    return RecommendationSessionResponse(
        session_id=session_id,
        total=len(
            result.recommendations
        ),
        items=result.recommendations,
    )


@router.get(
    "/{recommendation_id}",
    response_model=(
        RecommendationDetailResponse
    ),
)
def get_recommendation(
    recommendation_id: int,
    db: Session = Depends(get_db),
) -> RecommendationDetailResponse:
    """Return one persisted recommendation."""

    recommendation = db.get(
        Recommendation,
        recommendation_id,
    )

    if recommendation is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Không tìm thấy recommendation."
            ),
        )

    try:
        result = (
            RecommendationService().load(
                db=db,
                session_id=(
                    recommendation.session_id
                ),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    item = next(
        (
            candidate
            for candidate
            in result.recommendations
            if (
                candidate.product_id
                == recommendation.product_id
            )
        ),
        None,
    )

    if item is None:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Recommendation không còn "
                "khớp với dữ liệu session."
            ),
        )

    return RecommendationDetailResponse(
        id=recommendation.id,
        session_id=(
            recommendation.session_id
        ),
        product_id=(
            recommendation.product_id
        ),
        rank=recommendation.rank,
        item=item,
    )