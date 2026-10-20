"""Schemas used during deterministic product normalization."""

from datetime import datetime
from pydantic import BaseModel, Field


class NormalizedProductCandidate(BaseModel):
    """Normalized representation before product deduplication."""

    name: str
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
    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    shipping_fee: int | None = Field(default=None, ge=0)
    warranty: str | None = None
    voucher: dict | None = None
    observed_at: datetime | None = None

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
