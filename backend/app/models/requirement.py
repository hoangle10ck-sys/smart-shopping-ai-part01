"""Normalized shopping requirement persisted for one search session."""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Requirement(Base):
    """Structured requirement produced by the requirement analysis pipeline."""

    __tablename__ = "requirements"

    budget_metadata: Mapped["RequirementBudget | None"] = relationship(
        "RequirementBudget", uselist=False, cascade="all, delete-orphan",
    )

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
        unique=True,
        index=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    budget_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    budget_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(8),
        default="VND",
        nullable=False,
    )

    purpose: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    brands: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    requirements: Mapped[list[dict[str, object]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    excluded_requirements: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    sort_preference: Mapped[str] = mapped_column(
        String(40),
        default="best_match",
        nullable=False,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    session: Mapped["SearchSession"] = relationship(
        "SearchSession",
        back_populates="requirement",
    )


class RequirementBudget(Base):
    """No row means legacy min/max. Additive table; no backfill needed."""
    __tablename__ = 'requirement_budgets'
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey('requirements.id', ondelete='CASCADE'), primary_key=True,
    )
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
