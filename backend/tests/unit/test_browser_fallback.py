import builtins
import json
from datetime import datetime, timezone

import pytest

from app.schemas.collector import FetchStatus, SourceRegistration
from app.services.collectors.browser_product_page import BrowserProductPageCollector
from app.services.collectors.browser_renderer import (
    BrowserUnavailable,
    Crawl4AIRenderer,
    RenderedPage,
)
from app.services.collectors.product_page import looks_javascript_dependent


def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def source():
    return SourceRegistration(
        source_id="approved-shop",
        domain="shop.example",
        kind="product_page",
        permission_status="approved",
        permission_basis="Written approval for automated product collection.",
        terms_url="https://shop.example/terms",
        terms_checked_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
        enabled=True,
        allowed_paths=["/"],
        default_currency="VND",
        currency_minor_unit=0,
    )


class FakeRenderer:
    def __init__(self, page):
        self.page = page
        self.calls = []

    async def render(self, url):
        self.calls.append(url)
        if isinstance(self.page, Exception):
            raise self.page
        return self.page


def rendered_product_html():
    payload = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Laptop Rendered 16GB",
        "sku": "LAP-16",
        "offers": {
            "@type": "Offer",
            "price": "15900000",
            "priceCurrency": "VND",
        },
    }
    return "<main>Laptop Rendered 16GB</main><script type='application/ld+json'>" + json.dumps(payload) + "</script>"


def test_js_candidate_requires_an_empty_known_app_shell():
    assert looks_javascript_dependent("<div id='__next'></div><script>boot()</script>")
    assert not looks_javascript_dependent("<main>Ordinary article with enough visible server-rendered content</main>")


@pytest.mark.asyncio
async def test_browser_dom_reuses_deterministic_json_ld_extraction():
    renderer = FakeRenderer(RenderedPage(rendered_product_html(), "https://shop.example/p/laptop"))
    result = await BrowserProductPageCollector(
        renderer=renderer, max_bytes=100_000, max_content_chars=1000, resolver=public_dns
    ).fetch("https://shop.example/p/laptop", source())

    assert result.status == FetchStatus.SUCCESS
    assert result.observation.name == "Laptop Rendered 16GB"
    assert result.observation.offers[0].identity.external_sku_id == "LAP-16"
    assert result.observation.offers[0].sale_price == 15_900_000
    assert renderer.calls == ["https://shop.example/p/laptop"]


@pytest.mark.asyncio
async def test_browser_fallback_rejects_cross_host_final_url_and_captcha():
    external = FakeRenderer(RenderedPage(rendered_product_html(), "https://attacker.test/p"))
    rejected = await BrowserProductPageCollector(
        renderer=external, max_bytes=100_000, max_content_chars=1000, resolver=public_dns
    ).fetch("https://shop.example/p/laptop", source())
    assert rejected.status == FetchStatus.INVALID_URL

    captcha = FakeRenderer(RenderedPage("<h1>Verify you are human</h1>", "https://shop.example/p"))
    blocked = await BrowserProductPageCollector(
        renderer=captcha, max_bytes=100_000, max_content_chars=1000, resolver=public_dns
    ).fetch("https://shop.example/p", source())
    assert blocked.status == FetchStatus.ACCESS_RESTRICTED


@pytest.mark.asyncio
async def test_missing_optional_dependency_has_actionable_status(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "crawl4ai":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    renderer = Crawl4AIRenderer(timeout_seconds=2)
    with pytest.raises(BrowserUnavailable, match="requirements-browser.txt"):
        await renderer.render("https://shop.example/p")


@pytest.mark.asyncio
async def test_renderer_failure_is_structured_and_does_not_crash_pipeline():
    renderer = FakeRenderer(BrowserUnavailable("browser runtime missing"))
    result = await BrowserProductPageCollector(
        renderer=renderer, max_bytes=100_000, max_content_chars=1000, resolver=public_dns
    ).fetch("https://shop.example/p", source())
    assert result.status == FetchStatus.BROWSER_UNAVAILABLE
    assert "browser runtime missing" in result.failure.message
