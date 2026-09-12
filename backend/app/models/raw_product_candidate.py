"""Staging model for product data before normalization."""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.search_session import SearchSession
from app.models.source import Source


def utc_now() -> datetime:
    """Return current UTC time."""

    return datetime.now(timezone.utc)


class RawProductCandidate(Base):
    """Raw product candidate extracted from one search result."""

    __tablename__ = "raw_product_candidates"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            SearchSession.id,
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            Source.id,
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    search_query: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    payload: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )