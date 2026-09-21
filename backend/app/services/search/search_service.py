"""Search orchestration service."""

from __future__ import annotations

import asyncio
import time

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
        if self.settings.demo_mode:
            batches = await asyncio.gather(*(run_query(query) for query in queries))
        else:
            from app.models.requirement import Requirement
            from app.services.search.progressive_retrieval import ProgressiveRetriever
            requirement = db.scalar(select(Requirement).where(Requirement.session_id == session_id))
            retriever = ProgressiveRetriever(self.provider, self.image_resolver, self.settings)
            batches = await retriever.run(queries, requirement)
            diagnostics = retriever.diagnostics


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
            if not any((source.page_validation or {}).get('product_page_valid') for source in all_sources):
                warnings.append('Không tìm được trang bán sản phẩm đủ tin cậy trong giới hạn tìm kiếm.')

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


            if not self.settings.demo_mode:
                from app.services.extraction.product_page_validator import same_identity
                from app.services.normalization.product_normalizer import infer_product_category
                proof = source_item.page_validation or {"product_page_valid": False}
                if proof.get("product_page_valid"):
                    consistent = candidate is not None and same_identity(candidate.name, proof["name"])
                    model = proof.get("model")
                    if isinstance(model, dict): model = model.get("name")
                    candidate = RawProductCandidateData(
                        name=proof["name"], brand=proof.get("brand") or (candidate.brand if consistent else None),
                        model=model or (candidate.model if consistent else None),
                        category=(proof.get('category') if 'category_evidence' in proof else
                                  infer_product_category(proof["name"], proof.get('category') or (candidate.category if consistent else None))),
                        price_text=str(proof["price"]) + " VND",
                        rating_text=str(proof["rating"]) if proof.get("rating") is not None else None,
                        review_count_text=str(proof["review_count"]) if proof.get("review_count") is not None else None,
                        specifications={**(candidate.specifications if consistent else {}), **proof.get("specifications", {})},
                        availability=(proof.get("availability") or "").rsplit("/", 1)[-1].replace("OutOfStock", "out_of_stock").replace("InStock", "in_stock") or None,
                        product_url=proof["product_url"], source_domain=source_item.domain,
                        merchant=proof.get("merchant"), image_url=proof.get("image_url"),
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
