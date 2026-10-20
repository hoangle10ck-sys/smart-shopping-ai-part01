"""Live Crawl4AI smoke test against the explicitly provided scraping sandbox."""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.collector import SourceRegistration
from app.services.collectors.browser_renderer import Crawl4AIRenderer
from app.services.collectors.network_policy import build_pinned_http_client
from app.services.collectors.preflight import preflight_source


URL = "https://quotes.toscrape.com/js/"


async def main() -> int:
    source = SourceRegistration(
        source_id="quotes-to-scrape-browser-smoke",
        domain="quotes.toscrape.com",
        kind="product_page",
        permission_status="approved",
        permission_basis=(
            "The operator's official sites.toscrape.com landing page describes "
            "this host as a web-scraping sandbox with a JavaScript endpoint."
        ),
        terms_url="https://sites.toscrape.com/",
        robots_url="https://quotes.toscrape.com/robots.txt",
        terms_checked_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
        enabled=True,
        allowed_paths=["/js", "/robots.txt"],
    )
    async with build_pinned_http_client(
        allowed_domains=[source.domain], resolver=socket.getaddrinfo, timeout=12
    ) as client:
        preflight = await preflight_source(URL, source, client, min_interval_seconds=0)
    if not preflight.allowed:
        print(json.dumps({
            "status": "PREFLIGHT_DENIED",
            "reason": preflight.message,
        }))
        return 2

    page = await Crawl4AIRenderer(
        timeout_seconds=20,
        allowed_domain=source.domain,
        resolver=socket.getaddrinfo,
    ).render(URL)
    js_content_found = "Albert Einstein" in page.html and "class=\"quote\"" in page.html
    print(json.dumps({
        "status": "LIVE_SMOKE_OK" if js_content_found else "DOM_ASSERTION_FAILED",
        "url": URL,
        "final_url": page.final_url,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": page.elapsed_ms,
        "http_status": page.status_code,
        "network_requests": page.network_requests,
        "policy_denials": page.policy_denials,
        "dom_bytes": len(page.html.encode("utf-8")),
        "js_content_found": js_content_found,
    }))
    return 0 if js_content_found else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
