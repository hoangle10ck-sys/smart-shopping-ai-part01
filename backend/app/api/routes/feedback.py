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
from app.api.guest_owner import get_guest_owner, require_owned_session
from app.models.feedback import Feedback
from app.models.product import Product
from app.models.search_session import (
    SearchSession,
)
from app.models.user import User
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
    owner: User = Depends(get_guest_owner),
) -> FeedbackResponse:
    """Store recommendation usefulness feedback."""

    require_owned_session(db, payload.session_id, owner)

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
    owner: User = Depends(get_guest_owner),
) -> FeedbackListResponse:
    """Return all feedback for one search session."""

    require_owned_session(db, session_id, owner)

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
