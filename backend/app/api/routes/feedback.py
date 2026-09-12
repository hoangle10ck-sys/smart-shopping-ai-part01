"""Recommendation feedback API endpoints."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.feedback import Feedback
from app.models.product import Product
from app.models.search_session import (
    SearchSession,
)
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackListResponse,
    FeedbackResponse,
)


router = APIRouter(
    prefix="/api/feedback",
    tags=["Feedback"],
)


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_feedback(
    payload: FeedbackCreateRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Store recommendation usefulness feedback."""

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

    if payload.product_id is not None:
        product = db.get(
            Product,
            payload.product_id,
        )

        if product is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Không tìm thấy sản phẩm."
                ),
            )

    feedback = Feedback(
        session_id=payload.session_id,
        product_id=payload.product_id,
        is_helpful=payload.is_helpful,
        reason=payload.reason,
        comment=payload.comment,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return FeedbackResponse.model_validate(
        feedback
    )


@router.get(
    "/session/{session_id}",
    response_model=FeedbackListResponse,
)
def get_session_feedback(
    session_id: str,
    db: Session = Depends(get_db),
) -> FeedbackListResponse:
    """Return all feedback for one search session."""

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

    feedback_entries = list(
        db.scalars(
            select(Feedback)
            .where(
                Feedback.session_id
                == session_id
            )
            .order_by(
                Feedback.created_at.desc(),
                Feedback.id.desc(),
            )
        )
    )

    items = [
        FeedbackResponse.model_validate(
            item
        )
        for item in feedback_entries
    ]

    return FeedbackListResponse(
        session_id=session_id,
        total=len(items),
        items=items,
    )