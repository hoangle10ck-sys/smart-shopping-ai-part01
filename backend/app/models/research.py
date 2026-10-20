"""Historical research provenance; deliberately independent of merchant offers."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def now():
    return datetime.now(timezone.utc)


class ResearchProduct(Base):
    __tablename__ = "research_products"
    __table_args__ = (UniqueConstraint("dataset_id", "revision", "external_product_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), unique=True)
    dataset_id: Mapped[str] = mapped_column(String(200))
    revision: Mapped[str] = mapped_column(String(100))
    external_product_id: Mapped[str] = mapped_column(String(40))
    source_category: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(Text)
    input_sha256: Mapped[str] = mapped_column(String(64))
    record_sha256: Mapped[str] = mapped_column(String(64))
    line_number: Mapped[int] = mapped_column(Integer)
    metadata_fields: Mapped[dict] = mapped_column(JSON)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HistoricalPriceReference(Base):
    __tablename__ = "historical_price_references"
    __table_args__ = (CheckConstraint("currency = 'USD'"), CheckConstraint("reference_year = 2023"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    research_product_id: Mapped[int] = mapped_column(ForeignKey("research_products.id", ondelete="CASCADE"), unique=True)
    # Exact decimal text avoids SQLite floating-point rounding of cents.
    amount: Mapped[str] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source: Mapped[str] = mapped_column(Text)
    reference_year: Mapped[int] = mapped_column(default=2023)
    price_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    provenance: Mapped[dict] = mapped_column(JSON)


class ResearchImportRun(Base):
    __tablename__ = "research_import_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(200))
    revision: Mapped[str] = mapped_column(String(100))
    input_sha256: Mapped[str] = mapped_column(String(64))
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
