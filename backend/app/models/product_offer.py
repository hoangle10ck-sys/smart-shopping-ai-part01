"""Merchant-specific product offer model."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductOffer(Base):
    """Price and availability for a product at one merchant."""

    __tablename__ = "product_offers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    merchant: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    price: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(8),
        default="VND",
        nullable=False,
    )

    availability: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "sources.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    product_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="offers",
    )

    source: Mapped["Source | None"] = relationship(
        "Source",
        back_populates="offers",
    )