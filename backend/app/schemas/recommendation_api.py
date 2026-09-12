"""Schemas for recommendation read APIs."""

from pydantic import BaseModel, Field

from app.schemas.recommendation import (
    RecommendationItem,
    RecommendationDataSemantics,
)


class RecommendationSessionResponse(
    BaseModel
):
    """Recommendations belonging to one search session."""

    data_semantics: RecommendationDataSemantics = "snapshot"

    session_id: str

    total: int = 0

    items: list[
        RecommendationItem
    ] = Field(
        default_factory=list,
    )


class RecommendationDetailResponse(
    BaseModel
):
    """One persisted recommendation."""

    id: int

    data_semantics: RecommendationDataSemantics = "snapshot"

    session_id: str

    product_id: int

    rank: int

    item: RecommendationItem