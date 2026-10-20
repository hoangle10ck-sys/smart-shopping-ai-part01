"""Read-only database catalog source for unified search.

Replays existing Product/ProductOffer evidence into the current session as
RawProductCandidate rows so the legacy CandidateBuilder pipeline sees them.
Offers are matched by product_url during normalization, so replaying never
creates duplicate products or offers.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.product import Product
from app.models.product_offer import ProductOffer
from app.models.raw_product_candidate import RawProductCandidate
from app.models.search_session import utc_now
from app.schemas.requirement import RequirementData
from app.services.collectors.freshness import offer_freshness
from app.services.filter.hard_filter import normalized
from app.services.search.unified.base import SourceOutcome

CATALOG_SOURCE_NAME = "database_catalog"
CATALOG_SOURCE_DOMAIN = "catalog.internal"

# Maximum replay rows per run keeps session tables bounded.
MAX_REPLAY_ROWS = 30


def _category_matches(product_category: str | None, requirement: RequirementData) -> bool:
    """Loose token match; the hard filter makes the final decision later."""
    if not requirement.category:
        return True
    if not product_category:
        return False
    wanted = normalized(requirement.category)
    observed = normalized(product_category)
    return any(token in observed for token in wanted.split()) or any(
        token in wanted for token in observed.split()
    )


class DatabaseCatalogSource:
    """Search already-persisted catalog products with fresh offers."""

    name = CATALOG_SOURCE_NAME

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_available(self, db: Session) -> bool:
        return db.scalar(select(Product.id).limit(1)) is not None

    def search(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
    ) -> SourceOutcome:
        started = time.perf_counter()
        outcome = SourceOutcome(source_name=self.name)

        ttl = self.settings.product_offer_freshness_ttl_seconds

        # Newest offers first, bounded replay set.
        rows = list(
            db.execute(
                select(Product, ProductOffer)
                .join(ProductOffer, ProductOffer.product_id == Product.id)
                .order_by(ProductOffer.last_checked_at.desc())
                .limit(MAX_REPLAY_ROWS * 4)
            ).all()
        )

        existing_session_urls = set(
            db.scalars(
                select(RawProductCandidate.payload["product_url"].as_string()).where(
                    RawProductCandidate.session_id == session_id
                )
            )
        )

        seen_urls: set[str] = set()

        for product, offer in rows:
            if len(seen_urls) >= MAX_REPLAY_ROWS:
                break
            if not _category_matches(product.category, requirement):
                continue
            if not offer.product_url or offer.product_url in seen_urls:
                continue
            if offer.product_url in existing_session_urls:
                # Already replayed or ingested in this session; still counts
                # towards freshness for the fast-path decision.
                outcome.matched_products += 1
                if offer_freshness(offer, ttl) == "fresh":
                    outcome.fresh_products += 1
                continue

            seen_urls.add(offer.product_url)
            if offer_freshness(offer, ttl) == "fresh":
                outcome.fresh_products += 1
            outcome.matched_products += 1

            db.add(
                RawProductCandidate(
                    session_id=session_id,
                    source_id=offer.source_id,
                    search_query="[catalog-replay]",
                    payload=self._catalog_payload(product, offer),
                    created_at=utc_now(),
                )
            )
            outcome.ingested_rows += 1

        db.flush()
        outcome.duration_ms = (time.perf_counter() - started) * 1000
        if outcome.ingested_rows:
            outcome.warnings.append(
                f"Đã nạp {outcome.ingested_rows} sản phẩm từ catalog nội bộ (giá có thể cũ hơn thời điểm search)."
            )
        return outcome

    @staticmethod
    def _catalog_payload(product: Product, offer: ProductOffer) -> dict:
        """Rebuild an evidence payload the legacy pipeline accepts."""
        checked = offer.last_checked_at or product.updated_at
        return dict(
            name=product.name,
            category=product.category,
            brand=product.brand,
            model=product.model,
            price_text=str(offer.price) if offer.price is not None else None,
            rating_text=str(product.rating) if product.rating is not None else None,
            review_count_text=str(product.review_count) if product.review_count is not None else None,
            availability=offer.availability,
            product_url=offer.product_url,
            merchant=offer.merchant,
            source_domain=CATALOG_SOURCE_DOMAIN,
            specifications=dict(product.specifications or {}),
            image_url=product.image_url,
            currency=offer.currency or "VND",
            observed_at=checked,
            page_validation={
                "product_page_valid": True,
                "source_kind": "CATALOG",
                "name": product.name,
                "price": offer.price,
                "availability": offer.availability,
                "verified_from_catalog": True,
                "last_checked_at": checked.isoformat() if checked else None,
            },
            raw_text=None,
        )
