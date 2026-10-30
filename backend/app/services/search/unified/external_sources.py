"""External unified sources: demo, live Tavily, and fail-closed collectors.

The retained Demo adapter can reuse the legacy SearchService pipeline for
explicit test/compatibility calls. The unified shopping orchestrator excludes
it so fixtures cannot become purchase offers. Live reuses the full legacy
pipeline (extraction, normalization, dedup, persistence). Each source reports
availability honestly and never fabricates data when unavailable.
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import unquote, urlsplit

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.collector import SourceRegistration
from app.schemas.requirement import RequirementData
from app.services.collectors.source_registry import SourceRegistry
from app.services.search.mock_provider import MockSearchProvider
from app.services.search.search_service import SearchService
from app.services.search.multi_provider import MultiSearchProvider
from app.services.search.searxng_provider import SearXNGProvider
from app.services.search.base import SearchProviderError
from app.services.search.tavily_provider import TavilyProvider
from app.services.search.unified.base import SourceOutcome


class _PipelineSource:
    """Shared wrapper running the legacy SearchService for one provider."""

    name = "pipeline"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def _run_pipeline(
        self,
        *,
        db: Session,
        session_id: str,
        queries: list[str],
        direct_urls: list[str],
        outcome: SourceOutcome,
        provider=None,
    ) -> SourceOutcome:
        started = time.perf_counter()
        service = SearchService(provider=provider) if provider is not None else SearchService()
        try:
            response = await asyncio.wait_for(
                service.execute(
                    db=db,
                    session_id=session_id,
                    queries=queries,
                    direct_urls=direct_urls,
                ),
                timeout=self.settings.unified_source_timeout_seconds,
            )
            outcome.retrieval_diagnostics.extend(response.retrieval_diagnostics)
            outcome.matched_products = response.total_products
            outcome.ingested_rows = response.total_products
            outcome.warnings.extend(response.warnings)
        except Exception as exc:  # noqa: BLE001 - one dead source must not kill the run.
            # Exception text can contain URLs, response bodies, or credentials;
            # source outcomes are persisted in snapshots and returned by the API.
            outcome.error = type(exc).__name__
            outcome.warnings.append(
                f"Nguồn {self.name} không khả dụng trong lần tìm kiếm này."
            )
        outcome.duration_ms = (time.perf_counter() - started) * 1000
        return outcome


class DemoProductSource(_PipelineSource):
    """Deterministic offline data; only participates in Demo mode."""

    name = "demo_mock"

    def is_available(self, db: Session) -> bool:
        return bool(self.settings.demo_mode)

    async def search(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
        queries: list[str],
        direct_urls: list[str] | None = None,
    ) -> SourceOutcome:
        outcome = SourceOutcome(source_name=self.name)
        if not queries:
            outcome.error = "Không có truy vấn tìm kiếm."
            return outcome
        return await self._run_pipeline(
            db=db,
            session_id=session_id,
            queries=queries,
            direct_urls=direct_urls or [],
            outcome=outcome,
            provider=MockSearchProvider(),
        )

class LiveProductSource(_PipelineSource):
    """Configured-provider live source (Tavily and/or operator SearXNG)."""

    name = "configured_web_search"

    def is_available(self, db: Session) -> bool:
        # Tavily remains the opt-in source for the legacy page-fetching product
        # pipeline. SearXNG is discovery-only and is handled separately below.
        return bool(self.settings.tavily_api_key.strip())

    async def search(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
        queries: list[str],
        direct_urls: list[str] | None = None,
    ) -> SourceOutcome:
        outcome = SourceOutcome(source_name=self.name)
        if not queries:
            outcome.error = "Không có truy vấn tìm kiếm."
            return outcome
        return await self._run_pipeline(
            db=db,
            session_id=session_id,
            queries=queries,
            direct_urls=direct_urls or [],
            outcome=outcome,
            provider=MultiSearchProvider(include_searxng=False),
        )


class WebDiscoverySource:
    """Discover candidate URLs with SearXNG without fetching or ingesting pages."""

    name = "web_discovery"

    def __init__(self, provider=None) -> None:
        self.settings = get_settings()
        self.provider = provider

    def is_available(self, db: Session) -> bool:
        return bool(self.settings.searxng_base_url.strip())

    async def search(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
        queries: list[str],
        direct_urls: list[str] | None = None,
    ) -> SourceOutcome:
        del db, session_id, requirement, direct_urls
        outcome = SourceOutcome(source_name=self.name)
        if not self.is_available(None):
            outcome.available = False
            outcome.error = "SearXNG endpoint is not configured."
            return outcome

        bounded_queries = list(dict.fromkeys(
            query.strip() for query in queries if isinstance(query, str) and query.strip()
        ))[: max(1, self.settings.max_search_queries)]
        if not bounded_queries:
            outcome.error = "No discovery queries were supplied."
            return outcome

        started = time.perf_counter()
        timeout = max(0.05, self.settings.unified_source_timeout_seconds)
        limit = max(1, self.settings.max_results_per_query)
        registry_invalid = False
        try:
            registry = SourceRegistry.from_json(
                self.settings.collector_source_registry_json
            )
        except (TypeError, ValueError):
            # Discovery must remain available, but a malformed policy registry
            # can never make a candidate collector-eligible.
            registry = SourceRegistry([])
            registry_invalid = True

        async def discover(query: str):
            try:
                provider = self.provider or SearXNGProvider()
                return query, await asyncio.wait_for(
                    provider.search(query, limit), timeout=timeout
                ), None
            except asyncio.TimeoutError:
                return query, [], "timeout"
            except SearchProviderError as exc:
                return query, [], exc.kind
            except Exception as exc:  # noqa: BLE001 - isolate provider failures.
                return query, [], type(exc).__name__

        responses = await asyncio.gather(*(discover(query) for query in bounded_queries))
        seen_urls: set[str] = set()
        failures = []
        for _, results, failure in responses:
            if failure:
                failures.append(failure)
                continue
            for result in results:
                if result.url in seen_urls:
                    continue
                domain = (urlsplit(result.url).hostname or "").lower().rstrip(".")
                if not domain:
                    continue
                seen_urls.add(result.url)
                registration = registry.resolve_url(result.url)
                if registration is None:
                    review_status = "REVIEW_REQUIRED"
                    collector_eligible = False
                elif registration.permission_status == "restricted":
                    review_status = "RESTRICTED"
                    collector_eligible = False
                elif registration.permission_status != "approved":
                    review_status = "REVIEW_REQUIRED"
                    collector_eligible = False
                elif not registration.enabled:
                    review_status = "DISABLED"
                    collector_eligible = False
                else:
                    review_status = "APPROVED"
                    collector_eligible = bool(
                        registration.kind == "product_page"
                        and self.settings.collector_live_enabled
                        and self.settings.collector_policy_confirmed
                        and self._url_matches_registration(result.url, registration)
                    )
                outcome.web_candidates.append({
                    "title": result.title,
                    "url": result.url,
                    "domain": domain,
                    "status": "DISCOVERED",
                    "review_status": review_status,
                    "collector_eligible": collector_eligible,
                    "source": "searxng",
                })

        if registry_invalid:
            outcome.warnings.append(
                "Collector source registry is invalid; all candidates remain review-only."
            )

        if failures and not outcome.web_candidates:
            outcome.available = False
            failure_kinds = sorted(set(failures))
            outcome.error = f"SearXNG discovery failed ({', '.join(failure_kinds)})."
        elif failures:
            outcome.warnings.append(
                "Some web discovery queries failed; successful candidates were retained."
            )

        outcome.duration_ms = (time.perf_counter() - started) * 1000
        return outcome

    @staticmethod
    def _url_matches_registration(url: str, registration: SourceRegistration) -> bool:
        """Check static collector scope without resolving/fetching the URL."""

        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            return False
        if (
            parsed.scheme.lower() != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.fragment
        ):
            return False
        path = unquote(parsed.path or "/")
        if "\\" in path or any(segment in {".", ".."} for segment in path.split("/")):
            return False
        return any(
            path == prefix.rstrip("/")
            or path.startswith(prefix.rstrip("/") + "/")
            for prefix in registration.allowed_paths
        )
