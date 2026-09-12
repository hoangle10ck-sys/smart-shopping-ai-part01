"""Persist warnings from the latest search attempt without replacing results."""

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SearchExecutionState(Base):
    """Small companion record; existing session/product tables stay unchanged."""

    __tablename__ = "search_execution_states"

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("search_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
