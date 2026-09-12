"""Schemas used during deterministic product normalization."""

from pydantic import BaseModel, Field


class NormalizedProductCandidate(BaseModel):
    """Normalized representation before product deduplication."""

    name: str

    normalized_name: str

    category: str | None = None

    brand: str | None = None

    normalized_brand: str | None = None

    model: str | None = None

    normalized_model: str | None = None

    price: int | None = Field(
        default=None,
        ge=0,
    )

    currency: str = "VND"

    rating: float | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    review_count: int | None = Field(
        default=None,
        ge=0,
    )

    availability: str | None = None

    product_url: str | None = None

    source_domain: str | None = None

    specifications: dict[str, str] = Field(
        default_factory=dict,
    )

    raw_price_text: str | None = None

    raw_rating_text: str | None = None

    raw_review_count_text: str | None = None