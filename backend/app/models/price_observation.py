"""Immutable price history for an offer observation."""

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (UniqueConstraint("offer_id", "fingerprint", name="uq_price_observation_fingerprint"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("product_offers.id", ondelete="CASCADE"), index=True)
    crawl_run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id", ondelete="SET NULL"), index=True)
    listed_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listed_price_minor_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_price_minor_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency_minor_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="VND", nullable=False)
    shipping_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    voucher: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    availability: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    offer: Mapped["ProductOffer"] = relationship("ProductOffer", back_populates="price_observations")
    crawl_run: Mapped["CrawlRun | None"] = relationship("CrawlRun", back_populates="observations")
