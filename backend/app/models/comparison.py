"""Product comparison session model."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ComparisonSession(Base):
    """Stores a comparison request for two or three products."""

    __tablename__ = "comparison_sessions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "search_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    product_ids: Mapped[list[int]] = mapped_column(
        JSON,
        nullable=False,
    )

    result: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    session: Mapped["SearchSession"] = relationship(
        "SearchSession",
        back_populates="comparisons",
    )