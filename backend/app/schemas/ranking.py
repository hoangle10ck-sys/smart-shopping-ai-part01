"""Schemas for deterministic filtering, scoring and ranking."""

from pydantic import BaseModel, Field


class ScoringCandidate(BaseModel):
    """Product data required by hard filtering and scoring."""

    product_id: int

    name: str

    category: str | None = None

    brand: str | None = None

    model: str | None = None

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

    source_reliability: float = Field(
        default=50.0,
        ge=0,
        le=100,
    )

    specifications: dict[str, str] = Field(
        default_factory=dict,
    )


class FilterDecision(BaseModel):
    """Explain whether a product passed the hard filters."""

    product_id: int

    accepted: bool

    rejection_stage: str | None = None

    reasons: list[str] = Field(
        default_factory=list,
    )


class ScoreBreakdown(BaseModel):
    """Deterministic score components."""

    budget_score: float = Field(
        ge=0,
        le=100,
    )

    requirement_score: float = Field(
        ge=0,
        le=100,
    )

    purpose_score: float = Field(
        ge=0,
        le=100,
    )

    rating_score: float = Field(
        ge=0,
        le=100,
    )

    review_score: float = Field(
        ge=0,
        le=100,
    )

    source_score: float = Field(
        ge=0,
        le=100,
    )

    final_score: float = Field(
        ge=0,
        le=100,
    )


class RankedCandidate(BaseModel):
    """Candidate after scoring and ranking."""

    rank: int

    candidate: ScoringCandidate

    score: ScoreBreakdown