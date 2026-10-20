"""Canonical product model."""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.database import Base


def utc_now() -> datetime:
    """Return current UTC time."""

    return datetime.now(timezone.utc)


class Product(Base):
    """A canonical product independent of merchant-specific offers."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    brand: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        index=True,
    )

    normalized_name: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
        index=True,
    )

    image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rating: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    review_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    specifications: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    pros: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    cons: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    offers: Mapped[list["ProductOffer"]] = relationship(
        "ProductOffer",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )

    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    feedback_entries: Mapped[list["Feedback"]] = relationship(
        "Feedback",
        back_populates="product",
    )
