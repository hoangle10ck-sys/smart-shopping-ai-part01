"""API schemas for deterministic recommendations."""

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.evidence import (
    EvidenceReport,
    RequirementMatch,
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
RecommendationDataMode = Literal["demo", "live", "research", "unified"]


class UnifiedEnhancement(BaseModel):
    """Progress of optional background enrichment after an early unified response."""

    status: Literal["pending", "completed", "not_needed", "failed"]
    detail: str | None = None


class RecommendationItem(BaseModel):
    """One ranked recommendation returned to the client."""

    source_mode: Literal["HISTORICAL_RESEARCH"] | None = None
    historical_price: dict | None = None
    research_provenance: dict | None = None

    product_id: int
    variant_id: int | None = None
    offer_id: int | None = None
    platform: str | None = None
    freshness_status: str | None = None
    score_version: str = "legacy-v1"
    product_suitability: dict | None = None
    offer_quality: dict | None = None
    alternate_offers: list[dict] = Field(default_factory=list)

    rank: int = Field(
        ge=1,
    )

    name: str

    category: str | None = None

    brand: str | None = None

    model: str | None = None

    product_page_valid: bool | None = None
    price_type: Literal['CONCRETE'] | None = None
    variant: dict[str, str] | None = None
    source_observation_valid: bool | None = None
    verification_level: Literal['VERIFIED_PUBLIC_API', 'VERIFIED_CONTENT', 'VERIFIED_SEARCH_METADATA', 'UNVERIFIED', 'REJECTED'] | None = None
    product_page_confidence: float | None = Field(default=None, ge=0, le=100)
    image_source: str | None = None
    evidence_url: str | None = None
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

    requirement_matches: list[RequirementMatch] = Field(default_factory=list)

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

    # Unified-search provenance: which sources were checked and their outcomes.
    unified_sources: list[dict] = Field(default_factory=list)

    enhancement: UnifiedEnhancement | None = None
