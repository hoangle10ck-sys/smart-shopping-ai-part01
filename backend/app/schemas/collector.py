"""Typed contracts shared by compliant marketplace collectors."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FetchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_DATA = "PARTIAL_DATA"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    ROBOTS_DISALLOWED = "ROBOTS_DISALLOWED"
    SOURCE_NOT_PERMITTED = "SOURCE_NOT_PERMITTED"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    FETCH_ERROR = "FETCH_ERROR"
    INVALID_URL = "INVALID_URL"
    NOT_PRODUCT_PAGE = "NOT_PRODUCT_PAGE"
    BROWSER_UNAVAILABLE = "BROWSER_UNAVAILABLE"
    NOT_TESTED_LIVE = "NOT_TESTED_LIVE"


class CollectorFailure(BaseModel):
    code: FetchStatus
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = False
    http_status: int | None = Field(default=None, ge=100, le=599)
    retry_after_seconds: float | None = Field(default=None, ge=0)


class FieldEvidence(BaseModel):
    """Evidence for one value; legacy records may omit optional metadata."""

    field: str = Field(min_length=1, max_length=120)
    value: Any = None
    source_url: str | None = None
    json_path: str | None = Field(default=None, max_length=300)
    evidence_type: Literal["PUBLIC_API", "JSON_LD", "META", "VISIBLE_TEXT", "LEGACY", "UNKNOWN"] = "UNKNOWN"
    observed_at: datetime | None = None
    verification_status: Literal["VERIFIED", "PARTIAL", "UNVERIFIED", "STALE"] = "UNVERIFIED"


class VariantIdentity(BaseModel):
    """Source identity. Missing identifiers remain null; none are invented."""

    platform: str = Field(default="unknown", min_length=1, max_length=64)
    external_product_id: str | None = Field(default=None, max_length=160)
    external_shop_id: str | None = Field(default=None, max_length=160)
    external_sku_id: str | None = Field(default=None, max_length=160)
    attributes: dict[str, str] = Field(default_factory=dict)
    condition: str | None = Field(default=None, max_length=80)

    @field_validator("external_product_id", "external_shop_id", "external_sku_id", mode="before")
    @classmethod
    def blank_id_is_unknown(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


class PriceRange(BaseModel):
    minimum: int = Field(ge=0)
    maximum: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "PriceRange":
        if self.maximum < self.minimum:
            raise ValueError("price range maximum must be >= minimum")
        return self


class OfferObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: VariantIdentity
    merchant: str | None = Field(default=None, max_length=200)
    listed_price: int | None = Field(default=None, ge=0)
    sale_price: int | None = Field(default=None, ge=0)
    listed_price_minor_units: int | None = Field(default=None, ge=0)
    sale_price_minor_units: int | None = Field(default=None, ge=0)
    currency_minor_unit: int | None = Field(default=None, ge=0, le=4)
    price_range: PriceRange | None = None
    currency: str = Field(default="VND", min_length=3, max_length=8)
    shipping_fee: int | None = Field(default=None, ge=0)
    voucher: dict[str, Any] | None = None
    availability: str | None = Field(default=None, max_length=80)
    warranty: str | None = Field(default=None, max_length=300)
    seller_rating: float | None = Field(default=None, ge=0, le=5)
    product_url: str
    observed_at: datetime = Field(default_factory=utc_now)
    evidence: list[FieldEvidence] = Field(default_factory=list)


class ProductObservation(BaseModel):
    name: str | None = Field(default=None, max_length=500)
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=160)
    category: str | None = Field(default=None, max_length=120)
    product_rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    specifications: dict[str, str] = Field(default_factory=dict)
    image_url: str | None = None
    offers: list[OfferObservation] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)


class SourceFetchResult(BaseModel):
    status: FetchStatus
    source_url: str
    platform: str = Field(default="unknown", min_length=1, max_length=64)
    source_domain: str | None = None
    fetched_at: datetime = Field(default_factory=utc_now)
    robots_checked_at: datetime | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    content_text: str | None = Field(default=None, max_length=12000)
    observation: ProductObservation | None = None
    failure: CollectorFailure | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_payload_agree(self) -> "SourceFetchResult":
        if self.status in {FetchStatus.SUCCESS, FetchStatus.PARTIAL_DATA} and self.observation is None:
            raise ValueError("successful fetch requires an observation")
        if self.status not in {FetchStatus.SUCCESS, FetchStatus.PARTIAL_DATA} and self.failure is None:
            raise ValueError("failed fetch requires CollectorFailure")
        return self


class SourceRegistration(BaseModel):
    """Explicit per-host permission and adapter configuration."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    domain: str = Field(min_length=3, max_length=253)
    kind: Literal["woocommerce_store_api", "product_page"]
    permission_status: Literal["pending", "approved", "restricted"] = "pending"
    permission_basis: str | None = Field(default=None, max_length=1000)
    terms_url: str | None = Field(default=None, max_length=2048)
    terms_checked_at: datetime | None = None
    robots_url: str | None = Field(default=None, max_length=2048)
    enabled: bool = False
    allow_subdomains: bool = False
    allowed_paths: list[str] = Field(min_length=1, max_length=20)
    api_path: str = Field(default="/wp-json/wc/store/v1/products", max_length=500)
    default_currency: str | None = Field(default=None, min_length=3, max_length=8)
    currency_minor_unit: int | None = Field(default=None, ge=0, le=4)
    max_pages: int = Field(default=2, ge=1, le=5)
    max_products: int = Field(default=20, ge=1, le=50)

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        domain = value.strip().lower().rstrip(".")
        if (
            not domain
            or not domain.isascii()
            or "/" in domain
            or ":" in domain
            or "*" in domain
            or any(label.startswith("xn--") for label in domain.split("."))
        ):
            raise ValueError("domain must be a plain ASCII hostname")
        return domain

    @model_validator(mode="after")
    def enabled_source_has_permission(self) -> "SourceRegistration":
        if self.enabled and (
            self.permission_status != "approved"
            or not self.permission_basis
            or not self.permission_basis.strip()
            or self.terms_checked_at is None
        ):
            raise ValueError(
                "enabled sources require approved permission, a basis, and terms_checked_at"
            )
        for allowed_path in self.allowed_paths:
            parsed_allowed = urlsplit(allowed_path)
            if (
                not allowed_path.startswith("/")
                or allowed_path.startswith("//")
                or parsed_allowed.scheme
                or parsed_allowed.netloc
                or parsed_allowed.query
                or parsed_allowed.fragment
                or "\\" in allowed_path
                or any(segment in {".", ".."} for segment in unquote(parsed_allowed.path).split("/"))
            ):
                raise ValueError("allowed_paths must contain normalized absolute path prefixes")
        parsed_api_path = urlsplit(self.api_path)
        if (
            not self.api_path.startswith("/")
            or self.api_path.startswith("//")
            or parsed_api_path.scheme
            or parsed_api_path.netloc
            or parsed_api_path.query
            or parsed_api_path.fragment
            or "\\" in self.api_path
            or any(segment in {".", ".."} for segment in unquote(parsed_api_path.path).split("/"))
        ):
            raise ValueError("api_path must be a normalized path on the registered host")
        if self.kind == "woocommerce_store_api" and not any(
            self.api_path == prefix.rstrip("/")
            or self.api_path.startswith(prefix.rstrip("/") + "/")
            for prefix in self.allowed_paths
        ):
            raise ValueError("api_path must be covered by allowed_paths")
        return self


class DiscoveredProductURL(BaseModel):
    source_id: str
    url: str
    discovered_at: datetime = Field(default_factory=utc_now)
    discovery_method: Literal["user", "search", "storefront_api"]
    verification_status: Literal["DISCOVERED", "UNVERIFIED"] = "DISCOVERED"


class CrawlAttempt(BaseModel):
    source_id: str
    url: str
    attempted_at: datetime = Field(default_factory=utc_now)
    status: FetchStatus
    error_code: str | None = None
    message: str | None = None


class CollectorSearchResult(BaseModel):
    source_id: str
    query: str
    status: FetchStatus
    fetched_at: datetime = Field(default_factory=utc_now)
    robots_checked_at: datetime | None = None
    products: list[SourceFetchResult] = Field(default_factory=list)
    failure: CollectorFailure | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def failed_search_has_reason(self) -> "CollectorSearchResult":
        if self.status not in {FetchStatus.SUCCESS, FetchStatus.PARTIAL_DATA} and self.failure is None:
            raise ValueError("failed source search requires CollectorFailure")
        return self
