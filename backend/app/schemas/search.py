"""Pydantic schemas for web search and raw product extraction."""

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class SearchRequest(
    BaseModel
):
    """Request to execute generated search queries."""

    session_id: str = Field(
        min_length=1,
        max_length=36,
    )


class SearchSourceItem(
    BaseModel
):
    """One filtered source returned by a search provider."""

    title: str | None = None

    url: str

    domain: str | None = None

    content: str = ""

    image_url: str | None = None

    provider_score: (
        float
        | None
    ) = None

    reliability_score: float = Field(
        default=50.0,
        ge=0.0,
        le=100.0,
    )


class RawProductCandidateData(
    BaseModel
):
    """Product information before normalization."""

    name: str | None = None

    brand: str | None = None

    model: str | None = None

    price_text: str | None = None

    rating_text: str | None = None

    review_count_text: (
        str
        | None
    ) = None

    availability: (
        str
        | None
    ) = None

    product_url: (
        str
        | None
    ) = None

    source_domain: (
        str
        | None
    ) = None

    # Kept in raw payload too so we can
    # inspect/debug extraction later.
    image_url: (
        str
        | None
    ) = None

    specifications: dict[
        str,
        str,
    ] = Field(
        default_factory=dict,
    )

    raw_text: (
        str
        | None
    ) = None


class SearchExecutionResponse(
    BaseModel
):
    """Response after search and extraction."""

    session_id: str

    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"] | None = None

    queries: list[str] = Field(
        default_factory=list,
    )

    sources: list[
        SearchSourceItem
    ] = Field(
        default_factory=list,
    )

    raw_products: list[
        RawProductCandidateData
    ] = Field(
        default_factory=list,
    )

    total_results: int = 0

    total_sources: int = 0

    total_products: int = 0

    warnings: list[str] = Field(
        default_factory=list,
    )

    demo_mode: bool = False

    processing_time_ms: float = 0.0
