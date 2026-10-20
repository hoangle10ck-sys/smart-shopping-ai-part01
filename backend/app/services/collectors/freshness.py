from datetime import datetime, timezone
from app.models.product_offer import ProductOffer


def offer_freshness(offer: ProductOffer, ttl_seconds: int, now: datetime | None = None) -> str:
    checked = offer.last_verified_at or offer.last_checked_at
    if checked is None:
        return "UNKNOWN"
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    age = ((now or datetime.now(timezone.utc)) - checked).total_seconds()
    return "FRESH" if ttl_seconds > 0 and age <= ttl_seconds else "STALE"
