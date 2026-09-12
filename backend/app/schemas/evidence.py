"""Schemas for evidence validation and recommendation explanation."""

from typing import Literal

from pydantic import BaseModel, Field


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
        "gemini",
        "fallback",
    ] = "demo"