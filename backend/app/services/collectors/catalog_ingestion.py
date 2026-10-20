"""Batch ingestion for approved storefront sources.

This module deliberately reuses the collector contracts and the existing
normalization/persistence path.  It never invents catalog rows when a source
cannot be fetched or when collection is disabled by policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crawl_run import CrawlRun
from app.models.source import Source
from app.schemas.collector import FetchStatus, SourceFetchResult
from app.schemas.search import RawProductCandidateData
from app.services.collectors.service import CollectorService
from app.services.normalization.normalization_service import NormalizationService


DEFAULT_CATALOG_QUERIES = (
    "điện thoại smartphone",
    "laptop máy tính xách tay",
    "máy tính để bàn desktop",
    "tai nghe headphones",
)


@dataclass(slots=True)
class CatalogIngestionSummary:
    queries: list[str]
    fetched: int = 0
    persisted: int = 0
    products_created: int = 0
    offers_created: int = 0
    skipped: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)


class CatalogIngestionService:
    """Fetch a small approved catalog and upsert it into the main database."""

    def __init__(
        self,
        collector: CollectorService | None = None,
        normalization: NormalizationService | None = None,
    ) -> None:
        self.collector = collector or CollectorService()
        self.normalization = normalization or NormalizationService()

    async def ingest(
        self,
        db: Session,
        *,
        queries: list[str] | tuple[str, ...] = DEFAULT_CATALOG_QUERIES,
        direct_urls: list[str] | tuple[str, ...] = (),
    ) -> CatalogIngestionSummary:
        clean_queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
        clean_urls = list(dict.fromkeys(url.strip() for url in direct_urls if url.strip()))
        summary = CatalogIngestionSummary(queries=clean_queries)

        results: list[SourceFetchResult] = []
        for query in clean_queries:
            searches = await self.collector.search_registered_sources(query)
            for search in searches:
                results.extend(search.products)
                if search.failure is not None:
                    summary.failures.append(
                        {
                            "source": search.source_id,
                            "status": search.status.value,
                            "message": search.failure.message,
                        }
                    )

        for url in clean_urls:
            results.append(await self.collector.fetch(url))

        summary.fetched = len(results)
        if not results:
            summary.failures.append(
                {
                    "source": "registry",
                    "status": FetchStatus.NOT_TESTED_LIVE.value,
                    "message": (
                        "No approved enabled source or direct URL produced a result; "
                        "the database was not changed."
                    ),
                }
            )
            return summary
        try:
            for result in results:
                self._record_run(db, result)
                if result.status not in {FetchStatus.SUCCESS, FetchStatus.PARTIAL_DATA}:
                    summary.failures.append(
                        {
                            "source": result.source_url,
                            "status": result.status.value,
                            "message": result.failure.message if result.failure else "Fetch failed",
                        }
                    )
                    summary.skipped += 1
                    continue
                if result.observation is None or not result.observation.name:
                    summary.skipped += 1
                    continue

                source = self._get_or_create_source(db, result)
                candidates = self._candidates(result)
                if not candidates:
                    summary.skipped += 1
                    continue
                for candidate in candidates:
                    persisted = self.normalization.persist_candidate(
                        db=db,
                        candidate=candidate,
                        source_id=source.id,
                        image_url=result.observation.image_url,
                    )
                    if persisted is None:
                        summary.skipped += 1
                        continue
                    summary.persisted += 1
                    summary.products_created += int(persisted.created_product)
                    summary.offers_created += int(persisted.created_offer)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return summary

    @staticmethod
    def _record_run(db: Session, result: SourceFetchResult) -> None:
        db.add(
            CrawlRun(
                platform=result.platform,
                source_url=result.source_url,
                status=result.status.value,
                failure=result.failure.model_dump(mode="json") if result.failure else None,
                robots_checked_at=result.robots_checked_at,
                started_at=result.fetched_at,
                completed_at=result.fetched_at,
            )
        )

    @staticmethod
    def _get_or_create_source(db: Session, result: SourceFetchResult) -> Source:
        source = db.scalar(select(Source).where(Source.url == result.source_url))
        domain = result.source_domain or urlsplit(result.source_url).hostname
        if source is None:
            source = Source(
                url=result.source_url,
                domain=domain,
                title=result.observation.name if result.observation else None,
                reliability_score=80.0,
            )
            db.add(source)
            db.flush()
        else:
            source.domain = domain
            source.title = result.observation.name if result.observation else source.title
        return source

    @staticmethod
    def _candidates(result: SourceFetchResult) -> list[RawProductCandidateData]:
        observation = result.observation
        if observation is None or not observation.name:
            return []
        offers = observation.offers or [None]
        candidates: list[RawProductCandidateData] = []
        for offer in offers:
            amount = None
            if offer is not None and offer.currency == "VND" and offer.currency_minor_unit in {None, 0}:
                amount = offer.sale_price if offer.sale_price is not None else offer.listed_price
            candidates.append(
                RawProductCandidateData(
                    name=observation.name,
                    brand=observation.brand,
                    model=observation.model,
                    category=observation.category,
                    rating_text=str(observation.product_rating) if observation.product_rating is not None else None,
                    review_count_text=str(observation.review_count) if observation.review_count is not None else None,
                    specifications=observation.specifications,
                    image_url=observation.image_url,
                    merchant=offer.merchant if offer else None,
                    platform=result.platform,
                    external_product_id=offer.identity.external_product_id if offer else None,
                    external_shop_id=offer.identity.external_shop_id if offer else None,
                    external_sku_id=offer.identity.external_sku_id if offer else None,
                    variant_attributes=offer.identity.attributes if offer else {},
                    condition=offer.identity.condition if offer else None,
                    listed_price=offer.listed_price if offer else None,
                    sale_price=offer.sale_price if offer else None,
                    listed_price_minor_units=offer.listed_price_minor_units if offer else None,
                    sale_price_minor_units=offer.sale_price_minor_units if offer else None,
                    currency_minor_unit=offer.currency_minor_unit if offer else None,
                    currency=offer.currency if offer else "VND",
                    price_text=f"{amount} VND" if amount is not None else None,
                    price_min=offer.price_range.minimum if offer and offer.price_range else None,
                    price_max=offer.price_range.maximum if offer and offer.price_range else None,
                    shipping_fee=offer.shipping_fee if offer else None,
                    warranty=offer.warranty if offer else None,
                    voucher=offer.voucher if offer else None,
                    observed_at=offer.observed_at if offer else result.fetched_at,
                    availability=offer.availability if offer else None,
                    product_url=offer.product_url if offer else result.source_url,
                    evidence_url=result.source_url,
                    source_domain=result.source_domain or urlsplit(result.source_url).hostname,
                    page_validation={
                        "source_observation_valid": True,
                        "product_page_valid": False,
                        "source_kind": "COLLECTOR",
                        "name": observation.name,
                    },
                )
            )
        return candidates
