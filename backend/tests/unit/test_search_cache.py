"""Cache key equivalence, TTL boundaries and stale reference protection."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import SessionLocal
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.search_cache import SearchCacheEntry
from app.models.search_session import SearchSession, SearchSessionStatus
from app.schemas.requirement import RequirementData, RequirementItem
from app.services.cache import search_cache as module
from app.services.cache.search_cache import DatabaseSearchCache, as_utc, make_cache_key


def requirement():
    return RequirementData(category="Laptop", budget_max=15000000, purpose=["Học lập trình", "Văn phòng"],
                           brands=["ASUS", "Dell"], requirements=[RequirementItem(name="RAM", value="16GB", priority=5)])


def test_equivalent_requirements_share_key():
    first = requirement()
    second = first.model_copy(update={
        "category": "  LAPTOP ", "purpose": ["van phong", "  hoc   lap trinh "],
        "brands": [" dell ", "asus"], "confidence": 0.99,
        "requirements": [RequirementItem(name="ram", value="16gb", priority=5)],
    })
    assert make_cache_key(first) == make_cache_key(second)


@pytest.mark.parametrize("change", [
    {"budget_max": 20000000}, {"budget_min": 10000000}, {"category": "tai nghe"},
    {"purpose": ["chơi game"]}, {"brands": ["Apple"]}, {"currency": "USD"},
    {"excluded_requirements": ["nặng"]}, {"sort_preference": "price_asc"},
    {"requirements": [RequirementItem(name="RAM", value="8GB", priority=5)]},
    {"requirements": [RequirementItem(name="RAM", value="16GB", priority=1)]},
])
def test_different_requirements_have_different_keys(change):
    original = requirement()
    assert make_cache_key(original) != make_cache_key(original.model_copy(update=change))


def test_value_decimals_and_configuration_do_not_collide():
    first = requirement().model_copy(update={"requirements": [RequirementItem(name="weight", value="1.45kg")]})
    second = first.model_copy(update={"requirements": [RequirementItem(name="weight", value="145kg")]})
    assert make_cache_key(first) != make_cache_key(second)
    assert make_cache_key(first, scope={"top_k": 1}) != make_cache_key(first, scope={"top_k": 5})


@pytest.mark.parametrize("elapsed, hit", [(16, True), (17, False), (18, False)])
def test_ttl_boundary_and_no_sliding_expiry(monkeypatch, elapsed, hit):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)
    with SessionLocal() as db:
        session = SearchSession(raw_query="Laptop", status=SearchSessionStatus.COMPLETED)
        db.add(session)
        db.flush()
        snapshot = RecommendationSnapshot(session_id=session.id, created_at=now, payload={})
        db.add(snapshot)
        db.flush()
        cache = DatabaseSearchCache()
        assert cache.get(db, "missing") is None
        cache.put(db, "key", snapshot, ttl_seconds=17)
        db.commit()
        monkeypatch.setattr(module, "utc_now", lambda: now + timedelta(seconds=elapsed))
        assert (cache.get(db, "key") is not None) == hit
        entry = db.get(SearchCacheEntry, "key")
        assert entry is not None  # Expiry is read-only; no destructive cleanup.
        assert as_utc(entry.expires_at) == now + timedelta(seconds=17)


def test_replaced_or_in_progress_source_snapshot_invalidates_reference():
    with SessionLocal() as db:
        session = SearchSession(raw_query="Laptop", status=SearchSessionStatus.COMPLETED)
        db.add(session)
        db.flush()
        snapshot = RecommendationSnapshot(session_id=session.id, payload={})
        db.add(snapshot)
        db.flush()
        cache = DatabaseSearchCache()
        cache.put(db, "key", snapshot, 1800)
        db.commit()
        assert cache.get(db, "key") is not None
        session.status = SearchSessionStatus.PROCESSING
        db.commit()
        assert cache.get(db, "key") is None
        session.status = SearchSessionStatus.COMPLETED
        snapshot.created_at += timedelta(seconds=1)
        db.commit()
        assert cache.get(db, "key") is None
