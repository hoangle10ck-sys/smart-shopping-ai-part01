import asyncio
import json
from types import SimpleNamespace

import pytest

from app.services.search.base import SearchProviderError, SearchResult
from app.services.search.unified.external_sources import WebDiscoverySource


class FixtureProvider:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    async def search(self, query, max_results):
        self.queries.append((query, max_results))
        response = self.responses[query]
        if isinstance(response, Exception):
            raise response
        return response


def make_source(monkeypatch, provider, **overrides):
    settings = SimpleNamespace(**{
        "searxng_base_url": "http://searxng:8080",
        "unified_source_timeout_seconds": 1,
        "max_search_queries": 4,
        "max_results_per_query": 5,
        "collector_source_registry_json": "[]",
        "collector_live_enabled": False,
        "collector_policy_confirmed": False,
        **overrides,
    })
    monkeypatch.setattr(
        "app.services.search.unified.external_sources.get_settings",
        lambda: settings,
    )
    return WebDiscoverySource(provider=provider), settings


def test_discovery_returns_unverified_urls_without_product_ingestion(monkeypatch):
    provider = FixtureProvider({
        "máy tính": [
            SearchResult(
                title="Laptop thật",
                url="https://shop.example/laptop-x",
                content="Snippet có giá 1.000.000đ",
                image_url="https://img.example/laptop.jpg",
            ),
        ],
    })
    source, _ = make_source(monkeypatch, provider)

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["máy tính"]
    ))

    assert outcome.available is True
    assert outcome.matched_products == 0
    assert outcome.ingested_rows == 0
    assert outcome.web_candidates == [{
        "title": "Laptop thật",
        "url": "https://shop.example/laptop-x",
        "domain": "shop.example",
        "status": "DISCOVERED",
        "review_status": "REVIEW_REQUIRED",
        "collector_eligible": False,
        "source": "searxng",
    }]
    assert "Snippet có giá" not in str(outcome.summary())
    assert "image_url" not in str(outcome.summary())


def test_discovery_empty_results_are_successful_and_empty(monkeypatch):
    source, _ = make_source(monkeypatch, FixtureProvider({"máy tính": []}))

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["máy tính"]
    ))

    assert outcome.available is True
    assert outcome.error is None
    assert outcome.web_candidates == []
    assert outcome.ingested_rows == 0


def test_discovery_is_unavailable_without_an_endpoint(monkeypatch):
    provider = FixtureProvider({})
    source, _ = make_source(monkeypatch, provider, searxng_base_url="")

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["máy tính"]
    ))

    assert source.is_available(db=object()) is False
    assert outcome.available is False
    assert outcome.error == "SearXNG endpoint is not configured."
    assert provider.queries == []


def test_discovery_reports_sanitized_provider_failure(monkeypatch):
    provider = FixtureProvider({
        "máy tính": SearchProviderError(
            "sensitive response https://searxng.local/?token=secret",
            kind="http_error",
        ),
    })
    source, _ = make_source(monkeypatch, provider)

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["máy tính"]
    ))

    assert outcome.error == "SearXNG discovery failed (http_error)."
    assert outcome.web_candidates == []
    assert "secret" not in str(outcome.summary())


def test_discovery_timeout_is_partial_and_keeps_other_query_candidates(monkeypatch):
    class SlowOnOneQuery(FixtureProvider):
        async def search(self, query, max_results):
            if query == "slow":
                await asyncio.sleep(0.05)
            return await super().search(query, max_results)

    provider = SlowOnOneQuery({
        "slow": [],
        "máy tính": [SearchResult(title="Laptop", url="https://shop.example/laptop")],
    })
    source, _ = make_source(monkeypatch, provider, unified_source_timeout_seconds=0.01)

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["slow", "máy tính"]
    ))

    assert outcome.error is None
    assert len(outcome.web_candidates) == 1
    assert outcome.warnings == [
        "Some web discovery queries failed; successful candidates were retained."
    ]
    assert outcome.ingested_rows == 0


def test_searxng_is_not_an_ingestion_provider(monkeypatch):
    settings = SimpleNamespace(
        tavily_api_key="",
        searxng_base_url="http://searxng:8080",
        search_timeout_seconds=1,
        search_retry_count=0,
        collector_source_registry_json="[]",
        collector_live_enabled=False,
        collector_policy_confirmed=False,
    )
    monkeypatch.setattr(
        "app.services.search.unified.external_sources.get_settings",
        lambda: settings,
    )
    source = WebDiscoverySource(provider=FixtureProvider({}))
    assert source.is_available(db=object()) is True


@pytest.mark.parametrize(
    ("permission_status", "enabled", "expected_status", "expected_eligible"),
    [
        ("pending", False, "REVIEW_REQUIRED", False),
        ("restricted", False, "RESTRICTED", False),
        ("approved", False, "DISABLED", False),
        ("approved", True, "APPROVED", True),
    ],
)
def test_candidate_review_state_uses_registry_and_fails_closed(
    monkeypatch,
    permission_status,
    enabled,
    expected_status,
    expected_eligible,
):
    registration = {
        "source_id": "shop-example",
        "domain": "shop.example",
        "kind": "product_page",
        "permission_status": permission_status,
        "permission_basis": (
            "Reviewed permission record" if permission_status == "approved" else None
        ),
        "terms_checked_at": (
            "2026-10-29T00:00:00Z" if permission_status == "approved" else None
        ),
        "enabled": enabled,
        "allowed_paths": ["/"],
    }
    source, _ = make_source(
        monkeypatch,
        FixtureProvider({
            "laptop": [SearchResult(title="Laptop", url="https://shop.example/laptop")],
        }),
        collector_source_registry_json=json.dumps([registration]),
        collector_live_enabled=True,
        collector_policy_confirmed=True,
    )

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["laptop"]
    ))

    candidate = outcome.web_candidates[0]
    assert candidate["status"] == "DISCOVERED"
    assert candidate["review_status"] == expected_status
    assert candidate["collector_eligible"] is expected_eligible


def test_approved_candidate_stays_ineligible_until_both_global_gates_are_on(monkeypatch):
    registration = {
        "source_id": "shop-example",
        "domain": "shop.example",
        "kind": "product_page",
        "permission_status": "approved",
        "permission_basis": "Reviewed permission record",
        "terms_checked_at": "2026-10-29T00:00:00Z",
        "enabled": True,
        "allowed_paths": ["/"],
    }
    source, _ = make_source(
        monkeypatch,
        FixtureProvider({
            "laptop": [SearchResult(title="Laptop", url="https://shop.example/laptop")],
        }),
        collector_source_registry_json=json.dumps([registration]),
        collector_live_enabled=True,
        collector_policy_confirmed=False,
    )

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["laptop"]
    ))

    assert outcome.web_candidates[0]["review_status"] == "APPROVED"
    assert outcome.web_candidates[0]["collector_eligible"] is False


@pytest.mark.parametrize(
    ("url", "kind", "allowed_paths"),
    [
        ("http://shop.example/products/laptop", "product_page", ["/products"]),
        ("https://shop.example/products/laptop#details", "product_page", ["/products"]),
        ("https://shop.example/category/laptops", "product_page", ["/products"]),
        ("https://shop.example/products/laptop", "woocommerce_store_api", ["/"]),
    ],
)
def test_approved_source_candidate_must_match_static_collector_scope(
    monkeypatch, url, kind, allowed_paths
):
    registration = {
        "source_id": "shop-example",
        "domain": "shop.example",
        "kind": kind,
        "permission_status": "approved",
        "permission_basis": "Reviewed permission record",
        "terms_checked_at": "2026-10-29T00:00:00Z",
        "enabled": True,
        "allowed_paths": allowed_paths,
    }
    source, _ = make_source(
        monkeypatch,
        FixtureProvider({"laptop": [SearchResult(title="Laptop", url=url)]}),
        collector_source_registry_json=json.dumps([registration]),
        collector_live_enabled=True,
        collector_policy_confirmed=True,
    )

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["laptop"]
    ))

    assert outcome.web_candidates[0]["review_status"] == "APPROVED"
    assert outcome.web_candidates[0]["collector_eligible"] is False


def test_malformed_registry_keeps_discovered_candidate_review_only(monkeypatch):
    source, _ = make_source(
        monkeypatch,
        FixtureProvider({
            "laptop": [SearchResult(title="Laptop", url="https://shop.example/laptop")],
        }),
        collector_source_registry_json="not-json",
        collector_live_enabled=True,
        collector_policy_confirmed=True,
    )

    outcome = asyncio.run(source.search(
        db=object(), session_id="session", requirement=None, queries=["laptop"]
    ))

    assert outcome.web_candidates[0]["review_status"] == "REVIEW_REQUIRED"
    assert outcome.web_candidates[0]["collector_eligible"] is False
    assert any("registry is invalid" in warning for warning in outcome.warnings)
