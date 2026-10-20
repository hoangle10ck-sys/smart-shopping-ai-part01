from datetime import datetime, timedelta, timezone
from app.models import ProductOffer
from app.services.collectors.freshness import offer_freshness


def test_offer_freshness_uses_separate_ttl_and_never_calls_unknown_current():
    now = datetime.now(timezone.utc)
    assert offer_freshness(ProductOffer(product_id=1, last_checked_at=now), 3600, now) == "FRESH"
    assert offer_freshness(ProductOffer(product_id=1, last_checked_at=now - timedelta(hours=2)), 3600, now) == "STALE"
