"""Pydantic schemas for web search and raw product extraction."""

from datetime import datetime
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
    direct_urls: list[str] = Field(default_factory=list, max_length=5)
    source_platforms: list[Literal["shopee", "lazada"]] = Field(default_factory=lambda: ["shopee", "lazada"])
    refresh: bool = False
    # "platforms" keeps the legacy behaviour untouched; "auto" runs the
    # UnifiedSearchService which discovers every configured source.
    search_scope: Literal["platforms", "auto"] = "platforms"

    @classmethod
    def _unique_urls(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class SearchSourceItem(
    BaseModel
):
    """One filtered source returned by a search provider."""

    title: str | None = None

    url: str

    domain: str | None = None

    result_type: Literal["DIRECT_PRODUCT", "CATEGORY", "HOMEPAGE", "SEARCH_PAGE", "ARTICLE", "NEWS", "REVIEW", "UNKNOWN"] = "UNKNOWN"
    page_validation: dict | None = None
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

    page_validation: dict | None = None
    evidence_url: str | None = None
    merchant: str | None = None
    platform: str | None = None
    external_product_id: str | None = None
    external_shop_id: str | None = None
    external_sku_id: str | None = None
    variant_attributes: dict[str, str] = Field(default_factory=dict)
    condition: str | None = None
    listed_price: int | None = Field(default=None, ge=0)
    sale_price: int | None = Field(default=None, ge=0)
    listed_price_minor_units: int | None = Field(default=None, ge=0)
    sale_price_minor_units: int | None = Field(default=None, ge=0)
    currency_minor_unit: int | None = Field(default=None, ge=0, le=4)
    currency: str = "VND"
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    shipping_fee: int | None = Field(default=None, ge=0)
    warranty: str | None = None
    voucher: dict | None = None
    observed_at: datetime | None = None
    name: str | None = None

    # Supplied by product evidence, never by the user's requested category.
    category: str | None = None

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

    retrieval_diagnostics: list[dict] = Field(default_factory=list)

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
