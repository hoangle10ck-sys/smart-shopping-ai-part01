"""Schemas for recommendation feedback API."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class FeedbackCreateRequest(BaseModel):
    """Create feedback for a recommendation."""

    session_id: str = Field(
        min_length=1,
        max_length=36,
    )

    product_id: int | None = Field(
        default=None,
        gt=0,
    )

    is_helpful: bool

    reason: str | None = Field(
        default=None,
        max_length=120,
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator(
        "reason",
        "comment",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """Convert blank text to None."""

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value


class FeedbackResponse(BaseModel):
    """Feedback returned by API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    session_id: str

    product_id: int | None

    is_helpful: bool

    reason: str | None

    comment: str | None

    created_at: datetime


class FeedbackListResponse(BaseModel):
    """List of feedback for a search session."""

    session_id: str

    total: int

    items: list[FeedbackResponse]