"""Schemas for evidence validation and recommendation explanation."""

from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field


class RequirementMatch(BaseModel):
    """Deterministic assessment of one requested property, never LLM output."""

    name: str
    requested_value: str
    product_value: str | None = None
    status: Literal["matched", "unmet", "unknown"]
    reason: str


class FieldEvidence(BaseModel):
    """A source observation whose normalized value agrees with the snapshot."""

    field: str
    value: str | int | float
    source: str | None = None
    domain: str | None = None
    merchant: str | None = None
    url: str | None = None
    retrieved_at: datetime | None = None
    reliability: float | None = Field(default=None, ge=0, le=100)


class EvidenceBreakdown(BaseModel):
    """Individual deterministic data-confidence components."""

    source_reliability: float = Field(
        ge=0,
        le=100,
    )

    product_completeness: float = Field(
        ge=0,
        le=100,
    )

    offer_completeness: float = Field(
        ge=0,
        le=100,
    )

    consistency: float = Field(
        ge=0,
        le=100,
    )

    corroboration: float = Field(
        ge=0,
        le=100,
    )


class EvidenceReport(BaseModel):
    """Deterministic evidence-validation result."""

    fields: list[FieldEvidence] = Field(default_factory=list)

    confidence: float = Field(
        ge=0,
        le=100,
    )

    breakdown: EvidenceBreakdown

    source_count: int = Field(
        ge=0,
    )

    offer_count: int = Field(
        ge=0,
    )

    supporting_evidence: list[str] = Field(
        default_factory=list,
    )

    warnings: list[str] = Field(
        default_factory=list,
    )


class RecommendationExplanation(BaseModel):
    """Natural-language explanation grounded in validated evidence."""

    summary: str

    why_fit: list[str] = Field(
        default_factory=list,
    )

    tradeoffs: list[str] = Field(
        default_factory=list,
    )

    evidence_notes: list[str] = Field(
        default_factory=list,
    )

    generation_mode: Literal[
        "demo",
        "openai",
        "gemini",
        "fallback",
    ] = "demo"
