"""Schemas for product comparison API."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from app.schemas.product_image import ProductImageEvidence


ProductId = Annotated[
    int,
    Field(gt=0),
]


class ComparisonCreateRequest(BaseModel):
    """Request to compare two or three recommended products."""

    session_id: str = Field(
        min_length=1,
        max_length=36,
    )

    product_ids: list[ProductId] = Field(
        min_length=2,
        max_length=3,
    )

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(
        cls,
        value: list[int],
    ) -> list[int]:
        """Ensure every selected product is unique."""

        if len(set(value)) != len(value):
            raise ValueError(
                "product_ids không được trùng nhau."
            )

        return value


class ComparisonOfferItem(BaseModel):
    """Best merchant offer for one product."""

    merchant: str | None = None

    price: float | None = None

    currency: str = "VND"

    availability: str | None = None

    product_url: str | None = None


class ComparisonProductItem(BaseModel):
    """Product data used in comparison."""

    model_config = ConfigDict(extra="allow")

    product_id: int

    name: str | None = None

    category: str | None = None

    brand: str | None = None

    model: str | None = None

    image_url: str | None = None

    image_evidence: ProductImageEvidence | None = None

    rating: float | None = None

    review_count: int | None = None

    specifications: dict[str, Any] = Field(
        default_factory=dict,
    )

    pros: list[str] = Field(
        default_factory=list,
    )

    cons: list[str] = Field(
        default_factory=list,
    )

    ai_score: float | None = None

    confidence: float | None = None

    recommendation_rank: int | None = None

    best_offer: ComparisonOfferItem | None = None


class ComparisonResult(BaseModel):
    """Persisted comparison result."""

    winner_product_id: int

    summary: str

    criteria: list[str] = Field(
        default_factory=list,
    )

    products: list[ComparisonProductItem] = Field(
        default_factory=list,
    )

    product_comparison: list[dict[str, Any]] = Field(default_factory=list)

    offer_comparison: list[dict[str, Any]] = Field(default_factory=list)

    price_comparability: Literal["COMPARABLE", "NOT_COMPARABLE"] | None = None

    warnings: list[str] = Field(default_factory=list)

    data_semantics: str | None = None

    model_config = ConfigDict(extra="allow")


class ComparisonResponse(BaseModel):
    """Comparison session returned by API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    session_id: str

    product_ids: list[int]

    result: ComparisonResult | None

    created_at: datetime
