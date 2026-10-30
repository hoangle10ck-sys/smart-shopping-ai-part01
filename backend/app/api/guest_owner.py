"""Anonymous browser ownership for guest search sessions."""

from __future__ import annotations

import hashlib
import re
import secrets
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.comparison import ComparisonSession
from app.models.search_session import SearchSession
from app.models.user import User

GUEST_COOKIE_NAME = "shopping_guest"
GUEST_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
_GUEST_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _user_id_for_token(token: str) -> str:
    """Derive a database owner ID without storing the bearer token in the DB."""
    digest = hashlib.sha256(token.encode("ascii")).digest()[:16]
    return str(UUID(bytes=digest))


def _valid_token(value: str | None) -> str | None:
    return value if value and _GUEST_TOKEN.fullmatch(value) else None


def get_guest_owner(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    """Load or create the persistent anonymous owner for this browser."""
    token = _valid_token(request.cookies.get(GUEST_COOKIE_NAME))
    if token is None:
        token = secrets.token_urlsafe(32)

    owner_id = _user_id_for_token(token)
    owner = db.get(User, owner_id)
    if owner is None:
        owner = User(id=owner_id)
        db.add(owner)
        db.commit()

    settings = get_settings()
    response.set_cookie(
        key=GUEST_COOKIE_NAME,
        value=token,
        max_age=GUEST_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.app_env.lower() in {"production", "prod"},
        samesite="lax",
        path="/",
    )
    return owner


def get_existing_guest_owner(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve a guest cookie without creating an identity for public reads."""
    token = _valid_token(request.cookies.get(GUEST_COOKIE_NAME))
    return db.get(User, _user_id_for_token(token)) if token else None


def require_owned_session(
    db: Session,
    session_id: str,
    owner: User,
) -> SearchSession:
    """Return a session only to its guest owner; hide cross-owner existence."""
    session = db.scalar(
        select(SearchSession).where(
            SearchSession.id == session_id,
            SearchSession.user_id == owner.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy search session.")
    return session


def require_owned_comparison(
    db: Session,
    comparison_id: int,
    owner: User,
) -> ComparisonSession:
    """Return a comparison only when its parent session belongs to the guest."""
    comparison = db.get(ComparisonSession, comparison_id)
    if comparison is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy comparison.")
    require_owned_session(db, comparison.session_id, owner)
    return comparison
