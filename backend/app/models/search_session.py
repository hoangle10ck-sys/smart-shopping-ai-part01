"""Search session model."""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""

    return datetime.now(timezone.utc)


class SearchSessionStatus(str, Enum):
    """Lifecycle states required by the project specification."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SearchSession(Base):
    """One end-to-end shopping request from a user."""

    __tablename__ = "search_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    raw_query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[SearchSessionStatus] = mapped_column(
        SqlEnum(
            SearchSessionStatus,
            native_enum=False,
        ),
        default=SearchSessionStatus.PENDING,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    processing_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="search_sessions",
    )

    requirement: Mapped["Requirement | None"] = relationship(
        "Requirement",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    search_queries: Mapped[list["SearchQuery"]] = relationship(
        "SearchQuery",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    comparisons: Mapped[list["ComparisonSession"]] = relationship(
        "ComparisonSession",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    feedback_entries: Mapped[list["Feedback"]] = relationship(
        "Feedback",
        back_populates="session",
        cascade="all, delete-orphan",
    )