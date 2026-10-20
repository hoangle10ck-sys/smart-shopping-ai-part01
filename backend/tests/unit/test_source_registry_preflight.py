from datetime import datetime, timezone
import time

import httpx
import pytest
from pydantic import ValidationError

from app.schemas.collector import FetchStatus, SourceRegistration
from app.services.collectors.preflight import (
    MAX_ROBOTS_BYTES,
    pace_host,
    preflight_source,
    record_retry_after,
    validate_registered_url,
)
from app.services.collectors.source_registry import SourceRegistry


def approved_source(**overrides):
    values = {
        "source_id": "sample-shop",
        "domain": "shop.example",
        "kind": "product_page",
        "permission_status": "approved",
        "permission_basis": "Written merchant approval for this integration.",
        "terms_url": "https://shop.example/terms",
        "terms_checked_at": datetime(2026, 10, 15, tzinfo=timezone.utc),
        "enabled": True,
        "allowed_paths": ["/"],
    }
    values.update(overrides)
    return SourceRegistration(**values)


def public_dns(*args, **kwargs):
    return [(None, None, None, None, ("93.184.216.34", 443))]


def private_dns(*args, **kwargs):
    return [(None, None, None, None, ("127.0.0.1", 443))]


def test_source_registry_is_exact_and_fails_closed():
    source = approved_source()
    registry = SourceRegistry([source])
    assert registry.resolve_url("https://shop.example/product/1") == source
    assert registry.resolve_url("https://shop.example.attacker.test/product/1") is None
    assert registry.resolve_url("https://sub.shop.example/product/1") is None
    assert SourceRegistry([]).resolve_url("https://shop.example/product/1") is None


def test_enabled_registration_requires_review_and_duplicate_domains_fail():
    with pytest.raises(ValidationError):
        approved_source(terms_checked_at=None)
    with pytest.raises(ValueError, match="duplicate collector domain"):
        SourceRegistry([approved_source(), approved_source(source_id="other")])
    with pytest.raises(ValidationError, match="plain ASCII hostname"):
        approved_source(domain="xn--example-9za.test")


@pytest.mark.parametrize(
    "url",
    [
        "http://shop.example/item",
        "https://user:pass@shop.example/item",
        "https://shop.example:444/item",
        "https://shop.example.attacker.test/item",
    ],
)
def test_registered_url_rejects_unsafe_authority_and_host(url):
    with pytest.raises(ValueError):
        validate_registered_url(url, approved_source(), resolver=public_dns)


def test_registered_url_rejects_private_dns():
    with pytest.raises(ValueError, match="non-public"):
        validate_registered_url(
            "https://shop.example/item",
            approved_source(),
            resolver=private_dns,
        )


def test_registered_url_enforces_allowed_path_prefix_and_normalization():
    registered = approved_source(allowed_paths=["/products", "/robots.txt"])
    assert validate_registered_url(
        "https://shop.example/products/phone", registered, resolver=public_dns
    ).endswith("/products/phone")
    with pytest.raises(ValueError, match="path is not registered"):
        validate_registered_url(
            "https://shop.example/admin", registered, resolver=public_dns
        )
    with pytest.raises(ValueError, match="not normalized"):
        validate_registered_url(
            "https://shop.example/products/%2e%2e/admin",
            registered,
            resolver=public_dns,
        )


@pytest.mark.asyncio
async def test_preflight_requires_permission_and_robots_allowance():
    source = approved_source(domain="robots-policy.example")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            text="User-agent: *\nDisallow: /private\nAllow: /product/\n",
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        allowed = await preflight_source(
            "https://robots-policy.example/product/1",
            source,
            client,
            resolver=public_dns,
        )
        denied = await preflight_source(
            "https://robots-policy.example/private/1",
            source,
            client,
            resolver=public_dns,
        )
    assert allowed.allowed
    assert denied.status == FetchStatus.ROBOTS_DISALLOWED


@pytest.mark.asyncio
async def test_retry_after_blocks_next_request_even_without_normal_pacing():
    host = "retry-after.example"
    retry_after = record_retry_after(host, "0.1")
    started = time.monotonic()

    await pace_host(host, min_interval_seconds=0)

    assert retry_after == pytest.approx(0.1)
    assert time.monotonic() - started >= 0.07


@pytest.mark.asyncio
async def test_preflight_fails_closed_for_unknown_permission_and_robots_failure():
    source = approved_source(permission_status="pending", enabled=False)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as client:
        not_permitted = await preflight_source(
            "https://shop.example/product/1",
            source,
            client,
            resolver=public_dns,
        )
        blocked_robots = await preflight_source(
            "https://blocked-robots.example/product/1",
            approved_source(domain="blocked-robots.example"),
            client,
            resolver=public_dns,
        )
    assert not_permitted.status == FetchStatus.SOURCE_NOT_PERMITTED
    assert blocked_robots.status == FetchStatus.SOURCE_NOT_PERMITTED


@pytest.mark.asyncio
async def test_preflight_caches_robots_rules_and_records_check_time():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="User-agent: *\nAllow: /product/\n")

    registered = approved_source(domain="cache-shop.example")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await preflight_source(
            "https://cache-shop.example/product/1",
            registered,
            client,
            resolver=public_dns,
        )
        second = await preflight_source(
            "https://cache-shop.example/product/2",
            registered,
            client,
            resolver=public_dns,
        )

    assert first.allowed and second.allowed
    assert first.robots_checked_at is not None
    assert second.robots_checked_at == first.robots_checked_at
    assert calls == 1


@pytest.mark.asyncio
async def test_preflight_stops_when_robots_is_rate_limited():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    ) as client:
        result = await preflight_source(
            "https://rate-limited.example/product/1",
            approved_source(domain="rate-limited.example"),
            client,
            resolver=public_dns,
        )

    assert result.status == FetchStatus.ACCESS_RESTRICTED
    assert result.robots_checked_at is not None


@pytest.mark.asyncio
async def test_preflight_rejects_oversized_robots_response():
    def handler(request):
        return httpx.Response(200, content=b"x" * (MAX_ROBOTS_BYTES + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await preflight_source(
            "https://oversized-robots.example/product/1",
            approved_source(domain="oversized-robots.example"),
            client,
            resolver=public_dns,
        )

    assert result.status == FetchStatus.SOURCE_NOT_PERMITTED


@pytest.mark.asyncio
async def test_preflight_fails_closed_on_robots_timeout():
    def handler(request):
        raise httpx.ReadTimeout("request timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await preflight_source(
            "https://timeout-robots.example/product/1",
            approved_source(domain="timeout-robots.example"),
            client,
            resolver=public_dns,
        )

    assert result.status == FetchStatus.SOURCE_NOT_PERMITTED
    assert "could not be verified" in result.message
