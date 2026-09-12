"""API schemas for deterministic recommendations."""

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.evidence import (
    EvidenceReport,
    RecommendationExplanation,
)
from app.schemas.ranking import (
    FilterDecision,
    ScoreBreakdown,
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.schemas.search import (
    SearchExecutionResponse,
)


RecommendationDataSemantics = Literal["snapshot", "legacy_recomputed", "not_generated"]
RecommendationDataMode = Literal["demo", "live"]


class RecommendationItem(BaseModel):
    """One ranked recommendation returned to the client."""

    product_id: int

    rank: int = Field(
        ge=1,
    )

    name: str

    category: str | None = None

    brand: str | None = None

    model: str | None = None

    image_url: str | None = None

    price: int | None = None

    currency: str = "VND"

    merchant: str | None = None

    product_url: str | None = None

    availability: str | None = None

    last_checked_at: datetime | None = None

    rating: float | None = None

    review_count: int | None = None

    specifications: dict[str, str] = Field(
        default_factory=dict,
    )

    score: ScoreBreakdown

    confidence: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    evidence: EvidenceReport | None = None

    explanation: (
        RecommendationExplanation
        | None
    ) = None


class SearchPipelineResponse(
    SearchExecutionResponse
):
    """Full search response through explanation."""

    requirement: RequirementData

    candidates: list[
        ScoringCandidate
    ] = Field(
        default_factory=list,
    )

    filter_decisions: list[
        FilterDecision
    ] = Field(
        default_factory=list,
    )

    recommendations: list[
        RecommendationItem
    ] = Field(
        default_factory=list,
    )

    # Snapshot = latest successful run; legacy = consistently recomputed read-only view.
    data_semantics: RecommendationDataSemantics = "snapshot"

    # Historical provenance, unlike SearchExecutionResponse.demo_mode (runtime config).
    data_mode: RecommendationDataMode | None = None

    total_found: int = 0

    total_filtered: int = 0

    total_recommended: int = 0
