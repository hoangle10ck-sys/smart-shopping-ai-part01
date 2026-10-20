"""Merchant-specific product offer model."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductOffer(Base):
    """Price and availability for a product at one merchant."""

    __tablename__ = "product_offers"
    __table_args__ = (
        UniqueConstraint("platform", "external_product_id", "external_shop_id", "external_sku_id", name="uq_offer_external_identity"),
    )

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

    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    platform: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    external_product_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    external_shop_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    external_sku_id: Mapped[str | None] = mapped_column(String(160), nullable=True)

    merchant: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    price: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    listed_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listed_price_minor_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_price_minor_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency_minor_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voucher: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warranty: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(24), default="UNKNOWN", nullable=False)
    evidence_method: Mapped[str | None] = mapped_column(String(40), nullable=True)

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="offers",
    )

    source: Mapped["Source | None"] = relationship(
        "Source",
        back_populates="offers",
    )
    variant: Mapped["ProductVariant | None"] = relationship("ProductVariant", back_populates="offers")
    price_observations: Mapped[list["PriceObservation"]] = relationship(
        "PriceObservation", back_populates="offer", cascade="all, delete-orphan"
    )
