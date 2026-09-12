"""User model.

Authentication is intentionally not implemented in the MVP yet, but a user table
is kept so search history can later be associated with a real account.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""

    return datetime.now(timezone.utc)


class User(Base):
    """Application user placeholder for the MVP."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    search_sessions: Mapped[list["SearchSession"]] = relationship(
        "SearchSession",
        back_populates="user",
    )