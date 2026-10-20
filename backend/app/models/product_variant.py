"""Evidence-backed purchasable variant of a canonical product."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "identity_key", name="uq_variant_product_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    identity_key: Mapped[str] = mapped_column(String(500), nullable=False)
    attributes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    condition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    offers: Mapped[list["ProductOffer"]] = relationship("ProductOffer", back_populates="variant")

