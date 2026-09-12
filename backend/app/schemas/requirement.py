"""Pydantic schemas for shopping requirement analysis."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RequirementItem(BaseModel):
    """One user preference or product requirement."""

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Normalized requirement name.",
    )

    value: str = Field(
        min_length=1,
        max_length=200,
        description="Requirement value extracted from user input.",
    )

    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Priority from 1 (low) to 5 (very high).",
    )


class RequirementData(BaseModel):
    """Structured shopping requirement produced from natural language."""

    category: str | None = Field(
        default=None,
        max_length=120,
    )

    budget_min: int | None = Field(
        default=None,
        ge=0,
    )

    budget_max: int | None = Field(
        default=None,
        ge=0,
    )

    currency: str = Field(
        default="VND",
        min_length=3,
        max_length=8,
    )

    purpose: list[str] = Field(
        default_factory=list,
    )

    brands: list[str] = Field(
        default_factory=list,
    )

    requirements: list[RequirementItem] = Field(
        default_factory=list,
    )

    excluded_requirements: list[str] = Field(
        default_factory=list,
    )

    sort_preference: Literal[
        "best_match",
        "price_asc",
        "price_desc",
        "rating",
    ] = "best_match"

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    @field_validator(
        "category",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        """Convert blank strings to None."""

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    @model_validator(mode="after")
    def validate_budget_range(
        self,
    ) -> "RequirementData":
        """Ensure min budget does not exceed max budget."""

        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError(
                "budget_min cannot be greater than budget_max"
            )

        return self


class AnalyzeRequirementRequest(BaseModel):
    """Request body for requirement analysis."""

    raw_query: str = Field(
        min_length=3,
        max_length=2000,
    )


class ClarifyRequirementRequest(BaseModel):
    """User answer to one clarification question."""

    session_id: str = Field(
        min_length=1,
        max_length=36,
    )

    answer: str = Field(
        min_length=1,
        max_length=1000,
    )


class RequirementAnalysisResponse(BaseModel):
    """Response returned after analysis or clarification."""

    session_id: str

    requirement: RequirementData

    needs_clarification: bool

    missing_fields: list[str] = Field(
        default_factory=list,
    )

    clarification_question: str | None = None

    search_queries: list[str] = Field(
        default_factory=list,
    )