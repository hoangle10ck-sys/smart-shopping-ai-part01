"""Evidence required before a product image can be returned to shoppers."""

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class ProductImageEvidence(BaseModel):
    """Image bytes tied to a source record for the exact canonical product."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["VERIFIED"]
    image_url: AnyHttpUrl
    source_type: Literal[
        "RESEARCH_DATASET",
        "VERIFIED_PUBLIC_API",
        "VERIFIED_PRODUCT_PAGE",
    ]
    source_url: AnyHttpUrl
    identifier_type: Literal[
        "GTIN",
        "ASIN",
        "MPN",
        "MODEL",
        "DATASET_RECORD",
        "SOURCE_PRODUCT_ID",
        "PRODUCT_NAME",
    ]
    identifier_value: str = Field(min_length=1, max_length=160)
    verification_method: Literal[
        "SAME_SOURCE_RECORD",
        "IDENTIFIER_MATCHED_PAGE",
        "PUBLIC_API_IDENTIFIER_MATCH",
    ]
    checked_at: datetime
    content_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/avif",
    ]
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    license: str | None = Field(default=None, max_length=200)
    license_url: AnyHttpUrl | None = None

    @field_validator("identifier_value")
    @classmethod
    def non_whitespace_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier must not be blank")
        return normalized

    @field_validator("checked_at")
    @classmethod
    def timezone_aware_check_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("checked_at must include a timezone")
        return value
