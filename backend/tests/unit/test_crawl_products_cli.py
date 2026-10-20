import argparse
from types import SimpleNamespace

import pytest

from scripts import crawl_products


@pytest.mark.asyncio
async def test_preflight_fails_closed_before_network_for_unregistered_url(monkeypatch):
    monkeypatch.setattr(
        crawl_products,
        "get_settings",
        lambda: SimpleNamespace(collector_source_registry_json="[]"),
    )
    code, payload = await crawl_products.run_preflight("https://shop.example/product/1")
    assert code == 2
    assert payload["status"] == "SOURCE_NOT_PERMITTED"


@pytest.mark.asyncio
async def test_live_ingest_requires_explicit_acknowledgement():
    args = argparse.Namespace(live=False, max_products=5, max_pages=2, query=None, url=[])
    code, payload = await crawl_products.run_ingest(args)
    assert code == 2
    assert payload["status"] == "LIVE_ACK_REQUIRED"


@pytest.mark.asyncio
async def test_live_ingest_requires_both_policy_flags(monkeypatch):
    monkeypatch.setattr(
        crawl_products,
        "get_settings",
        lambda: SimpleNamespace(collector_live_enabled=True, collector_policy_confirmed=False),
    )
    args = argparse.Namespace(live=True, max_products=5, max_pages=2, query=None, url=[])
    code, payload = await crawl_products.run_ingest(args)
    assert code == 2
    assert payload["status"] == "SOURCE_NOT_PERMITTED"
