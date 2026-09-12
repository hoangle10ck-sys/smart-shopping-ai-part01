"""Latest successful recommendation view, independent of mutable offers."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecommendationSnapshot(Base):
    """Additive companion table; a successful rerun replaces only its session view."""

    __tablename__ = "recommendation_snapshots"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("search_sessions.id", ondelete="CASCADE"), primary_key=True,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
