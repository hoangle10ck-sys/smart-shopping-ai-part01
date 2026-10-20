"""External unified sources: demo, live Tavily, and fail-closed collectors.

Demo and live reuse the full legacy SearchService pipeline (extraction,
normalization, dedup, persistence) so unified runs never diverge from the
well-tested legacy behaviour. Each source reports availability honestly and
never fabricates data when unavailable.
"""

from __future__ import annotations

import asyncio
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.requirement import RequirementData
from app.services.search.mock_provider import MockSearchProvider
from app.services.search.search_service import SearchService
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
            outcome.matched_products = response.total_products
            outcome.ingested_rows = response.total_products
            outcome.warnings.extend(response.warnings)
        except Exception as exc:  # noqa: BLE001 - one dead source must not kill the run.
            outcome.error = f"{type(exc).__name__}: {exc}"
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
    """Tavily-backed live source; available only outside Demo mode with a key."""

    name = "tavily_live"

    def is_available(self, db: Session) -> bool:
        return (
            not self.settings.demo_mode
            and bool(self.settings.tavily_api_key.strip())
        )

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
            provider=TavilyProvider(),
        )


class CollectorProductSource:
    """Shopee/Lazada collectors stay fail-closed unless policy explicitly allows."""

    name = "marketplace_collector"

    def __init__(self) -> None:
        self.settings = get_settings()

    def is_available(self, db: Session) -> bool:
        if not (self.settings.collector_live_enabled and self.settings.collector_policy_confirmed):
            return False
        return bool(self.settings.collector_source_registry_json.strip() not in {"", "[]", "[ ]"})

    def search(
        self,
        *,
        db: Session,
        session_id: str,
        requirement: RequirementData,
        queries: list[str],
        direct_urls: list[str] | None = None,
    ) -> SourceOutcome:
        # Policy-gated; when enabled this would route through CollectorService
        # with the approved registry. Until then availability stays False and
        # the unified run simply reports the source as skipped.
        outcome = SourceOutcome(source_name=self.name, available=False)
        outcome.error = "Collector đang khóa theo chính sách nguồn (ACCESS_RESTRICTED)."
        return outcome
