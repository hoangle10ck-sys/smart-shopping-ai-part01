"""Schemas for product detail API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProductOfferItem(BaseModel):
    """One merchant offer for a product."""

    id: int

    merchant: str | None = None

    price: int | None = None

    currency: str = "VND"

    availability: str | None = None

    source_id: int | None = None

    source_domain: str | None = None

    source_title: str | None = None

    source_reliability_score: float | None = None

    product_url: str | None = None

    last_checked_at: datetime


class ProductDetailResponse(BaseModel):
    """Full product information for frontend."""

    id: int

    name: str | None = None

    category: str | None = None

    brand: str | None = None

    model: str | None = None

    normalized_name: str | None = None

    image_url: str | None = None

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

    offers: list[ProductOfferItem] = Field(
        default_factory=list,
    )

    created_at: datetime

    updated_at: datetime