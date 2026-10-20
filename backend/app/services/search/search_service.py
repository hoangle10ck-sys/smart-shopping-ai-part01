"""Search orchestration service."""

from __future__ import annotations

import asyncio
import time
from app.services.performance import current_trace

from sqlalchemy import (
    delete,
    select,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    get_settings,
)

from app.models.raw_product_candidate import (
    RawProductCandidate,
)


from app.models.source import (
    Source,
)

from app.schemas.search import (
    RawProductCandidateData,
    SearchExecutionResponse,
    SearchSourceItem,
)

from app.services.extraction.product_extraction_service import (
    ProductExtractionService,
)

from app.services.extraction.product_image_resolver import (
    ProductImageResolver,
)

from app.services.normalization.normalization_service import (
    NormalizationService,
)

from app.services.search.base import (
    SearchProvider,
    SearchProviderError,
)

from app.services.search.mock_provider import (
    MockSearchProvider,
)

from app.services.search.source_filter import (
    SourceFilter,
)

from app.services.search.tavily_provider import (
    TavilyProvider,
)


class AllSearchQueriesFailed(SearchProviderError):
    """No query succeeded; callers must preserve the previous search results."""

    def __init__(self, warnings: list[str]) -> None:
        super().__init__("Tất cả truy vấn tìm kiếm đều thất bại.")
        self.warnings = list(warnings)


def get_search_provider(
) -> SearchProvider:
    """Return Demo or Tavily search provider."""

    settings = (
        get_settings()
    )

    if settings.demo_mode:
        return MockSearchProvider()

    return TavilyProvider()


class SearchService:
    """
    Complete search pipeline.

    Order:

    Tavily
        ↓
    SourceFilter
        ↓
    sales-page / image verification (Live)
        ↓
    ProductExtraction (verified direct pages first)
        ↓
    database persistence

    Query/result limits and resolver concurrency/timeouts bound network work.
    """

    def _offer_entries(self, entries):
        """Keep page sources singular; expand only concrete verified variant offers."""
        from app.services.extraction.dealer_offers import concrete_proofs
        for query, source in entries:
            variants = (source.page_validation or {}).get('variant_offers')
            if not self.settings.demo_mode and variants:
                for proof in concrete_proofs(source.page_validation):
                    yield query, source.model_copy(update={'page_validation':proof,'image_url':proof.get('image_url')})
            else:
                yield query, source

    @staticmethod
    def _collector_sources(result):
        """Convert collector evidence without labeling API observations as pages."""
        from urllib.parse import urlsplit

        observation = result.observation
        if observation is None:
            return []
        is_public_api = any(
            evidence.evidence_type == "PUBLIC_API"
            for evidence in observation.evidence
        )
        evidence_url = next(
            (
                evidence.source_url
                for evidence in observation.evidence
                if evidence.source_url
            ),
            result.source_url,
        )
        sources = []
        for offer in observation.offers or [None]:
            amount = None
            if offer is not None:
                amount = (
                    offer.sale_price
                    if offer.sale_price is not None
                    else offer.listed_price
                )
            vnd_price = (
                amount
                if offer is not None
                and offer.currency == "VND"
                and offer.currency_minor_unit in {None, 0}
                else None
            )
            product_url = offer.product_url if offer is not None else result.source_url
            proof = {
                "product_page_valid": not is_public_api,
                "source_observation_valid": is_public_api,
                "source_kind": "PUBLIC_API" if is_public_api else "PRODUCT_PAGE",
                "name": observation.name,
                "brand": observation.brand,
                "model": observation.model,
                "category": observation.category,
                "price": vnd_price,
                "price_type": "CONCRETE" if vnd_price is not None else None,
                "rating": observation.product_rating,
                "review_count": observation.review_count,
                "specifications": observation.specifications,
                "image_url": observation.image_url,
                "image_source": "PUBLIC_API" if is_public_api and observation.image_url else None,
                "availability": offer.availability if offer else None,
                "product_url": product_url,
                "evidence_url": evidence_url,
                "merchant": offer.merchant if offer else None,
                "variant": offer.identity.attributes if offer else {},
                "platform": result.platform,
                "external_product_id": offer.identity.external_product_id if offer else None,
                "external_shop_id": offer.identity.external_shop_id if offer else None,
                "external_sku_id": offer.identity.external_sku_id if offer else None,
                "listed_price": offer.listed_price if offer else None,
                "sale_price": offer.sale_price if offer else None,
                "listed_price_minor_units": offer.listed_price_minor_units if offer else None,
                "sale_price_minor_units": offer.sale_price_minor_units if offer else None,
                "currency_minor_unit": offer.currency_minor_unit if offer else None,
                "currency": offer.currency if offer else "VND",
                "price_min": (
                    offer.price_range.minimum
                    if offer and offer.price_range and offer.currency == "VND"
                    else None
                ),
                "price_max": (
                    offer.price_range.maximum
                    if offer and offer.price_range and offer.currency == "VND"
                    else None
                ),
                "shipping_fee": offer.shipping_fee if offer else None,
                "warranty": offer.warranty if offer else None,
                "voucher": offer.voucher if offer else None,
                "observed_at": offer.observed_at if offer else result.fetched_at,
                "robots_checked_at": result.robots_checked_at,
                "verification_level": (
                    "VERIFIED_PUBLIC_API" if is_public_api else "VERIFIED_CONTENT"
                ),
                "product_page_confidence": 100.0,
            }
            sources.append(
                SearchSourceItem(
                    title=observation.name,
                    url=result.source_url,
                    domain=result.source_domain or urlsplit(result.source_url).hostname,
                    result_type="DIRECT_PRODUCT",
                    page_validation=proof,
                    content=result.content_text or "",
                    image_url=observation.image_url,
                    reliability_score=80.0,
                )
            )
        return sources

    def __init__(
        self,
        provider: (
            SearchProvider
            | None
        ) = None,
    ) -> None:

        self.settings = (
            get_settings()
        )

        self.provider = (
            provider
            if provider is not None
            else get_search_provider()
        )

        self.source_filter = (
            SourceFilter()
        )

        self.extractor = (
            ProductExtractionService()
        )

        self.image_resolver = (
            ProductImageResolver(
                concurrency=8,
            )
        )

        self.normalization_service = (
            NormalizationService()
        )


    async def execute(
        self,
        *,
        db: Session,
        session_id: str,
        queries: list[str],
        direct_urls: list[str] | None = None,
        source_platforms: list[str] | None = None,
    ) -> SearchExecutionResponse:
        """Execute complete search pipeline."""

        started_at = (
            time.perf_counter()
        )

        warnings: list[
            str
        ] = []


        # We do not want to hold a SQLite transaction while
        # waiting for Tavily or external product websites.
        db.rollback()


        # =====================================================
        # SEARCH ONE QUERY
        # =====================================================

        async def run_query(
            query: str,
        ) -> tuple[
            str,
            list[
                SearchSourceItem
            ],
            str | None,
        ]:

            try:
                raw_results = (
                    await self.provider.search(
                        query,
                        self.settings
                        .max_results_per_query,
                    )
                )

                filtered = (
                    self.source_filter.filter(
                        raw_results
                    )
                )

                return (
                    query,
                    filtered,
                    None,
                )

            except Exception as exc:
                return (
                    query,
                    [],
                    (
                        "Không thể tìm kiếm cho query "
                        f"'{query}' [{getattr(exc, 'kind', 'unexpected_error')}]: {exc}"
                    ),
                )


        # =====================================================
        # SEARCH ALL QUERIES CONCURRENTLY
        # =====================================================

        diagnostics = []
        direct_urls = list(dict.fromkeys(direct_urls or []))[: self.settings.collector_max_urls]
        source_platforms = source_platforms or ["shopee", "lazada"]
        direct_batches = []
        collector_results = []
        if direct_urls:
            from app.services.collectors import CollectorService
            results = await asyncio.gather(*(CollectorService().fetch(url) for url in direct_urls))
            collector_results = list(results)
            from app.schemas.collector import FetchStatus
            for result in results:
                if result.platform in {"shopee", "lazada"} and result.platform not in source_platforms:
                    direct_batches.append((result.source_url, [], "Nguồn URL trực tiếp không nằm trong lựa chọn nền tảng."))
                    continue
                if result.status not in {FetchStatus.SUCCESS, FetchStatus.PARTIAL_DATA} or result.observation is None:
                    direct_batches.append((result.source_url, [], f"Direct collector {result.status.value}: {result.failure.message if result.failure else ''}"))
                    continue
                sources = self._collector_sources(result)
                direct_batches.append((result.source_url, sources, None))
        if direct_urls and direct_batches and any(warning is None for _, _, warning in direct_batches):
            batches = direct_batches
        elif self.settings.demo_mode:
            batches = [*direct_batches, *(await asyncio.gather(*(run_query(query) for query in queries)))]
        else:
            from app.models.requirement import Requirement
            from app.services.search.progressive_retrieval import ProgressiveRetriever
            requirement = db.scalar(select(Requirement).where(Requirement.session_id == session_id))
            retriever = ProgressiveRetriever(self.provider, self.image_resolver, self.settings)
            batches = await retriever.run(queries, requirement)
            diagnostics = retriever.diagnostics
            batches = [*direct_batches, *batches]

        if not self.settings.demo_mode:
            from app.schemas.collector import FetchStatus
            from app.services.collectors import CollectorService

            collector_service = CollectorService()
            registered_batches = await asyncio.gather(
                *(
                    collector_service.search_registered_sources(query)
                    for query in queries
                )
            )
            for query, search_results in zip(queries, registered_batches):
                for search_result in search_results:
                    collector_results.extend(search_result.products)
                    if search_result.failure is not None:
                        from app.schemas.collector import SourceFetchResult

                        source = collector_service.registry.get(search_result.source_id)
                        if source is not None:
                            collector_results.append(
                                SourceFetchResult(
                                    status=search_result.status,
                                    source_url=f"https://{source.domain}{source.api_path}",
                                    source_domain=source.domain,
                                    platform=source.source_id,
                                    fetched_at=search_result.fetched_at,
                                    robots_checked_at=search_result.robots_checked_at,
                                    failure=search_result.failure,
                                )
                            )
                        warnings.append(
                            f"Storefront API {search_result.source_id} "
                            f"{search_result.status.value}: {search_result.failure.message}"
                        )
                    if search_result.warnings:
                        warnings.extend(search_result.warnings)
                    sources = [
                        source
                        for product in search_result.products
                        for source in self._collector_sources(product)
                    ]
                    if sources or search_result.status in {
                        FetchStatus.SUCCESS,
                        FetchStatus.PARTIAL_DATA,
                    }:
                        batches.append((query, sources, None))
                    else:
                        batches.append(
                            (
                                query,
                                [],
                                f"Storefront API {search_result.source_id} "
                                f"{search_result.status.value}",
                            )
                        )


        # A successful empty response is different from a failed provider call.
        # Abort before deleting raw candidates or updating any product/offer.
        if batches and all(warning is not None for _, _, warning in batches):
            raise AllSearchQueriesFailed(
                [warning for _, _, warning in batches if warning is not None]
            )

        total_results = sum(
            len(
                results
            )
            for (
                _,
                results,
                _,
            )
            in batches
        )


        # =====================================================
        # DEDUP SOURCES
        # =====================================================

        all_sources: list[
            SearchSourceItem
        ] = []

        source_entries: list[
            tuple[
                str,
                SearchSourceItem,
            ]
        ] = []

        seen_urls: set[
            str
        ] = set()


        for (
            query,
            sources,
            warning,
        ) in batches:

            if warning:
                warnings.append(
                    warning
                )

            for source_item in (
                sources
            ):

                if (
                    source_item.url
                    in seen_urls
                ):
                    continue

                seen_urls.add(
                    source_item.url
                )

                all_sources.append(
                    source_item
                )

                source_entries.append(
                    (
                        query,
                        source_item,
                    )
                )


        # =====================================================
        # EXTRACT PRODUCT FIRST
        #
        # This is the important optimization.
        #
        # OLD:
        # 20 web sources -> crawl images of 20 pages
        #
        # NEW:
        # 20 sources -> extract -> maybe 6-10 valid products
        # -> crawl only those pages.
        # =====================================================

        if not self.settings.demo_mode:
            # Verify actual page content before constructing any sales offer.
            source_entries.sort(key=lambda entry: entry[1].result_type != 'DIRECT_PRODUCT')
            all_sources.sort(key=lambda source: source.result_type != 'DIRECT_PRODUCT')
            if not any(
                (source.page_validation or {}).get("product_page_valid")
                or (source.page_validation or {}).get("source_observation_valid")
                for source in all_sources
            ):
                warnings.append('Không tìm được trang bán sản phẩm đủ tin cậy trong giới hạn tìm kiếm.')

        extraction_started = time.perf_counter()
        candidate_entries: list[
            tuple[
                str,
                SearchSourceItem,
                RawProductCandidateData,
            ]
        ] = []


        for (
            query,
            source_item,
        ) in self._offer_entries(source_entries):

            try:
                candidate = (
                    self.extractor.extract(
                        source_item
                    )
                )

            except Exception:
                candidate = None


            if (
                not self.settings.demo_mode
                or (source_item.page_validation or {}).get("product_page_valid")
                or (source_item.page_validation or {}).get("source_observation_valid")
            ):
                from app.services.extraction.product_page_validator import same_identity
                from app.services.normalization.product_normalizer import infer_product_category
                proof = source_item.page_validation or {"product_page_valid": False}
                source_is_verified = (
                    proof.get("product_page_valid")
                    or proof.get("source_observation_valid")
                )
                if source_is_verified:
                    consistent = candidate is not None and same_identity(candidate.name, proof["name"])
                    model = proof.get("model")
                    if isinstance(model, dict): model = model.get("name")
                    price = proof.get("price")
                    currency = proof.get("currency") or "VND"
                    candidate = RawProductCandidateData(
                        name=proof["name"], brand=proof.get("brand") or (candidate.brand if consistent else None),
                        model=model or (candidate.model if consistent else None),
                        category=(proof.get('category') if 'category_evidence' in proof else
                                  infer_product_category(proof["name"], proof.get('category') or (candidate.category if consistent else None))),
                        price_text=(f"{price} VND" if price is not None and currency == "VND" else None),
                        rating_text=str(proof["rating"]) if proof.get("rating") is not None else None,
                        review_count_text=str(proof["review_count"]) if proof.get("review_count") is not None else None,
                        specifications={**(candidate.specifications if consistent else {}), **proof.get("specifications", {})},
                        availability=(proof.get("availability") or "").rsplit("/", 1)[-1].replace("OutOfStock", "out_of_stock").replace("InStock", "in_stock") or None,
                        product_url=proof["product_url"], source_domain=source_item.domain,
                        merchant=proof.get("merchant"), image_url=proof.get("image_url"),
                        platform=proof.get("platform"), external_product_id=proof.get("external_product_id"),
                        external_shop_id=proof.get("external_shop_id"), external_sku_id=proof.get("external_sku_id"),
                        variant_attributes=proof.get("variant") or {}, listed_price=proof.get("listed_price"),
                        sale_price=proof.get("sale_price"),
                        listed_price_minor_units=proof.get("listed_price_minor_units"),
                        sale_price_minor_units=proof.get("sale_price_minor_units"),
                        currency_minor_unit=proof.get("currency_minor_unit"),
                        currency=currency,
                        price_min=proof.get("price_min"), price_max=proof.get("price_max"),
                        shipping_fee=proof.get("shipping_fee"), voucher=proof.get("voucher"), observed_at=proof.get("observed_at"),
                        warranty=proof.get("warranty"),
                        evidence_url=proof.get("evidence_url"), page_validation=proof,
                        raw_text=source_item.content,
                    )
                elif candidate is not None:
                    candidate.product_url = None
                    candidate.image_url = None
                    candidate.price_text = None
                    candidate.page_validation = proof
                    candidate.evidence_url = source_item.url
                    warnings.append("Source retained as evidence only: " + source_item.url)
            if candidate is None:
                continue

            if (
                self.settings.enable_llm_extraction_fallback
                and len(candidate.specifications) < 2
                and not (source_item.page_validation or {}).get("source_observation_valid")
            ):
                try:
                    from app.services.extraction.llm_spec_fallback import LLMSpecFallback
                    extra_specs = await LLMSpecFallback().extract(candidate.raw_text or source_item.content)
                    candidate.specifications = {**candidate.specifications, **{
                        key: value for key, value in extra_specs.items() if key not in candidate.specifications
                    }}
                except Exception as exc:
                    warnings.append(
                        "LLM spec fallback failed "
                        f"({type(exc).__name__}); deterministic evidence was retained."
                    )


            candidate_entries.append(
                (
                    query,
                    source_item,
                    candidate,
                )
            )


        # =====================================================
        # IMAGE RESOLUTION
        #
        # Only valid product candidates are allowed here.
        # =====================================================

        raw_products: list[
            RawProductCandidateData
        ] = []


        for (
            _,
            source_item,
            candidate,
        ) in candidate_entries:

            candidate.image_url = (
                source_item.image_url
            )

            raw_products.append(
                candidate
            )


        # =====================================================
        # DATABASE WRITE PHASE
        #
        # All slow external HTTP work is finished before here.
        # =====================================================

        trace = current_trace.get()
        if trace is not None:
            trace.timings["extraction_ms"] += (time.perf_counter() - extraction_started) * 1000

        if collector_results:
            from app.models.crawl_run import CrawlRun
            for result in collector_results:
                db.add(CrawlRun(platform=result.platform, source_url=result.source_url,
                    status=result.status.value,
                    failure=result.failure.model_dump(mode="json") if result.failure else None,
                    robots_checked_at=result.robots_checked_at,
                    started_at=result.fetched_at, completed_at=result.fetched_at))

        db.execute(
            delete(
                RawProductCandidate
            ).where(
                RawProductCandidate.session_id
                == session_id
            )
        )


        for (
            query,
            source_item,
            candidate,
        ) in candidate_entries:

            # -------------------------------------------------
            # SOURCE
            # -------------------------------------------------

            source_model = (
                db.scalar(
                    select(
                        Source
                    ).where(
                        Source.url
                        == source_item.url
                    )
                )
            )


            if (
                source_model
                is None
            ):
                source_model = (
                    Source(
                        url=(
                            source_item.url
                        ),

                        domain=(
                            source_item.domain
                        ),

                        title=(
                            source_item.title
                        ),

                        reliability_score=(
                            source_item
                            .reliability_score
                        ),
                    )
                )

                db.add(
                    source_model
                )

                db.flush()

            else:
                source_model.domain = (
                    source_item.domain
                )

                source_model.title = (
                    source_item.title
                )

                source_model.reliability_score = (
                    source_item
                    .reliability_score
                )


            # -------------------------------------------------
            # RAW CANDIDATE
            # -------------------------------------------------

            db.add(
                RawProductCandidate(
                    session_id=(
                        session_id
                    ),

                    source_id=(
                        source_model.id
                    ),

                    search_query=(
                        query
                    ),

                    payload=(
                        candidate
                        .model_dump(
                            mode="json"
                        )
                    ),
                )
            )


            # -------------------------------------------------
            # PRODUCT + OFFER
            # -------------------------------------------------

            self.normalization_service.persist_candidate(
                db=db,

                candidate=(
                    candidate
                ),

                source_id=(
                    source_model.id
                ),

                image_url=(
                    source_item.image_url
                ),
            )


        db.commit()


        processing_time_ms = (
            (
                time.perf_counter()
                - started_at
            )
            * 1000
        )


        return SearchExecutionResponse(
            retrieval_diagnostics=diagnostics,
            session_id=(
                session_id
            ),

            queries=(
                queries
            ),

            sources=(
                all_sources
            ),

            raw_products=(
                raw_products
            ),

            total_results=(
                total_results
            ),

            total_sources=len(
                all_sources
            ),

            total_products=len(
                raw_products
            ),

            warnings=(
                warnings
            ),

            demo_mode=(
                self.settings.demo_mode
            ),

            processing_time_ms=(
                round(
                    processing_time_ms,
                    2,
                )
            ),
        )
