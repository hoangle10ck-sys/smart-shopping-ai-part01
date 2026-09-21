"""Deterministic keys and TTL storage; no provider calls or Product/Offer writes."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.search_cache import SearchCacheEntry
from app.models.search_session import SearchSession, SearchSessionStatus
from app.schemas.requirement import RequirementData
from app.services.llm.client import normalize_text


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo on roundtrip; stored timestamps are always UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def make_cache_key(requirement: RequirementData, *, scope: dict | None = None) -> str:
    """Normalize case/accents/whitespace/order, retaining values and priorities.

    Punctuation in values is significant: 1.45kg must not collide with 145kg.
    Confidence is analysis metadata, not a filtering/scoring input.
    """
    def texts(values):
        return sorted(normalize_text(value) for value in values)

    payload = {
        "version": 1, "scope": scope or {},
        "category": normalize_text(requirement.category or ""),
        "budget_min": requirement.budget_min, "budget_max": requirement.budget_max,
        "budget_mode": requirement.budget_mode, "budget_target": requirement.budget_target,
        "preferred_min": requirement.preferred_min, "preferred_max": requirement.preferred_max,
        "currency": normalize_text(requirement.currency),
        "purpose": texts(requirement.purpose), "brands": texts(requirement.brands),
        "requirements": sorted((normalize_text(item.name), normalize_text(item.value), item.priority)
                               for item in requirement.requirements),
        "excluded_requirements": texts(requirement.excluded_requirements),
        "sort_preference": requirement.sort_preference,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class SearchCache(Protocol):
    def get(self, db: Session, key: str) -> SearchCacheEntry | None: ...
    def put(self, db: Session, key: str, snapshot: RecommendationSnapshot, ttl_seconds: int) -> None: ...


class DatabaseSearchCache:
    """The caller owns transactions. Reads neither renew TTL nor delete rows."""

    def get(self, db: Session, key: str) -> SearchCacheEntry | None:
        entry = db.get(SearchCacheEntry, key, populate_existing=True)
        if entry is None or as_utc(entry.expires_at) <= utc_now():
            return None
        source = db.get(SearchSession, entry.session_id, populate_existing=True)
        if source is None or source.status != SearchSessionStatus.COMPLETED:
            # Raw evidence may be changing during a rerun. Reuse only a settled run.
            return None
        snapshot = db.get(RecommendationSnapshot, entry.session_id, populate_existing=True)
        if snapshot is None or as_utc(snapshot.created_at) != as_utc(entry.snapshot_created_at):
            # A rerun replaced the source snapshot; never reuse it under an old key.
            return None
        return entry

    def put(self, db: Session, key: str, snapshot: RecommendationSnapshot, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        now = utc_now()
        entry = db.get(SearchCacheEntry, key)
        if entry is None:
            entry = SearchCacheEntry(key=key)
            db.add(entry)
        entry.session_id = snapshot.session_id
        entry.snapshot_created_at = snapshot.created_at
        entry.created_at = now
        entry.expires_at = now + timedelta(seconds=ttl_seconds)
