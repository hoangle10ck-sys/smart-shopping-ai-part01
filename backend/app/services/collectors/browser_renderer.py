"""Optional, bounded browser rendering for approved JavaScript product pages."""

from __future__ import annotations

import asyncio
import os
import socket
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from app.services.collectors.egress_proxy import BrowserEgressProxy
from app.services.collectors.network_policy import resolve_public_addresses


@dataclass(frozen=True, slots=True)
class RenderedPage:
    html: str
    final_url: str
    elapsed_ms: int | None = None
    status_code: int | None = None
    network_requests: int = 0
    policy_denials: int = 0


class BrowserRenderer(Protocol):
    async def render(self, url: str) -> RenderedPage: ...


class BrowserUnavailable(RuntimeError):
    """The optional renderer or its browser runtime is unavailable."""


async def _watch_child_resources(
    stop: asyncio.Event,
    violations: list[str],
    *,
    memory_limit_mb: int,
    process_limit: int,
) -> None:
    """Terminate the browser process tree if aggregate bounds are exceeded."""
    try:
        import psutil
    except ImportError:
        violations.append("psutil is unavailable; browser limits cannot be enforced")
        return
    root = psutil.Process()
    baseline = {child.pid for child in root.children(recursive=True)}
    while not stop.is_set():
        children = [
            child for child in root.children(recursive=True)
            if child.pid not in baseline and child.is_running()
        ]
        try:
            rss = sum(child.memory_info().rss for child in children)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            rss = 0
        reason = None
        if len(children) > process_limit:
            reason = f"browser process limit exceeded ({len(children)}>{process_limit})"
        elif rss > memory_limit_mb * 1024 * 1024:
            reason = f"browser memory limit exceeded ({rss}>{memory_limit_mb} MiB)"
        if reason:
            violations.append(reason)
            for child in reversed(children):
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.05)
        except TimeoutError:
            pass


class Crawl4AIRenderer:
    """Render exactly one URL with the self-hosted Crawl4AI Python package.

    Permission, robots, URL and response validation remain the caller's job.
    The browser never performs clicks, form submissions, downloads or link
    traversal through this adapter.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        allowed_domain: str | None = None,
        resolver=socket.getaddrinfo,
        memory_limit_mb: int = 768,
        process_limit: int = 12,
    ) -> None:
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))
        self.allowed_domain = allowed_domain.rstrip(".").lower() if allowed_domain else None
        self.resolver = resolver
        self.memory_limit_mb = max(256, min(int(memory_limit_mb), 2048))
        self.process_limit = max(4, min(int(process_limit), 32))

    async def render(self, url: str) -> RenderedPage:
        os.environ["CRAWL4AI_CHROMIUM_SANDBOX"] = "true"
        os.environ.setdefault(
            "CRAWL4_AI_BASE_DIRECTORY",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.runtime")),
        )
        try:
            from crawl4ai import (
                AsyncWebCrawler,
                BrowserConfig,
                CacheMode,
                CrawlerRunConfig,
                ProxyConfig,
            )
        except ImportError as exc:
            raise BrowserUnavailable(
                "Crawl4AI is not installed. Install backend/requirements-browser.txt "
                "and run crawl4ai-setup before enabling browser collection."
            ) from exc
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".").lower()
        if (
            parsed.scheme != "https"
            or parsed.port not in {None, 443}
            or not host
            or (self.allowed_domain is not None and host != self.allowed_domain)
        ):
            raise BrowserUnavailable("Browser egress policy denied the navigation URL.")
        try:
            pinned_ip = resolve_public_addresses(host, 443, resolver=self.resolver)[0]
        except ValueError as exc:
            raise BrowserUnavailable(f"Browser egress policy denied DNS: {exc}") from exc
        # Crawl4AI otherwise starts Chromium with --no-sandbox. This process-wide
        # setting is applied immediately before construction and never reverted to
        # an unsafe value.
        started = time.monotonic()
        blocked_resources: list[str] = []
        resource_violations: list[str] = []
        try:
            async with BrowserEgressProxy(host, resolver=self.resolver) as proxy:
                browser_config = BrowserConfig(
                    headless=True,
                    verbose=False,
                    text_mode=False,
                    light_mode=True,
                    memory_saving_mode=True,
                    enable_stealth=False,
                    ignore_https_errors=False,
                    accept_downloads=False,
                    proxy_config=ProxyConfig(server=f"http://127.0.0.1:{proxy.port}"),
                    extra_args=[
                        f"--host-resolver-rules=EXCLUDE 127.0.0.1,MAP {host} {pinned_ip},MAP * ~NOTFOUND",
                        "--proxy-bypass-list=<-loopback>",
                        "--disable-features=AsyncDns,DnsOverHttps",
                        f"--renderer-process-limit={max(1, self.process_limit - 3)}",
                        f"--js-flags=--max-old-space-size={self.memory_limit_mb // 2}",
                    ],
                )
                run_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=int(self.timeout_seconds * 1000),
                    wait_until="domcontentloaded",
                    scan_full_page=False,
                    check_robots_txt=False,
                    max_retries=0,
                    exclude_all_images=True,
                    process_iframes=False,
                    capture_network_requests=True,
                )
                async with asyncio.timeout(self.timeout_seconds + 2.0):
                    resource_stop = asyncio.Event()
                    watchdog = asyncio.create_task(_watch_child_resources(
                        resource_stop,
                        resource_violations,
                        memory_limit_mb=self.memory_limit_mb,
                        process_limit=self.process_limit,
                    ))
                    try:
                        async with AsyncWebCrawler(config=browser_config) as crawler:
                            async def protect_page(page, *, context, **kwargs):
                                async def route_request(route, request):
                                    request_url = urlsplit(request.url)
                                    request_host = (request_url.hostname or "").rstrip(".").lower()
                                    if request_url.scheme in {"data", "blob", "about"} or (
                                        request_url.scheme == "https"
                                        and request_host == host
                                        and request_url.port in {None, 443}
                                    ):
                                        await route.continue_()
                                    else:
                                        blocked_resources.append(request.url[:500])
                                        await route.abort("blockedbyclient")
                                await context.route("**/*", route_request)
                                return page

                            crawler.crawler_strategy.set_hook(
                                "on_page_context_created", protect_page
                            )
                            result = await crawler.arun(url=url, config=run_config)
                    finally:
                        resource_stop.set()
                        await watchdog
                denials = proxy.denials
                connections = proxy.connections
        except (TimeoutError, OSError) as exc:
            detail = ""
            if "proxy" in locals():
                detail = f" (connections={proxy.connections}, denials={proxy.denials}, last={proxy.last_denial})"
            raise BrowserUnavailable(
                f"Crawl4AI renderer failed: {type(exc).__name__}{detail}"
            ) from exc

        if not getattr(result, "success", False):
            message = str(getattr(result, "error_message", "render failed"))[:300]
            raise BrowserUnavailable(
                f"Crawl4AI renderer failed: {message} "
                f"(connections={proxy.connections}, denials={proxy.denials}, last={proxy.last_denial})"
            )
        if resource_violations:
            raise BrowserUnavailable(resource_violations[0])
        html = getattr(result, "html", None)
        if not isinstance(html, str) or not html.strip():
            raise BrowserUnavailable("Crawl4AI returned no rendered HTML.")
        final_url = getattr(result, "url", None)
        status_code = getattr(result, "status_code", None)
        if status_code in {401, 403, 429}:
            raise BrowserUnavailable(f"Crawl4AI access restricted (HTTP {status_code}).")
        if denials:
            raise BrowserUnavailable(
                "Browser egress policy denied a network request "
                f"(denials={denials}, last={proxy.last_denial})."
            )
        requests = getattr(result, "network_requests", None)
        return RenderedPage(
            html=html,
            final_url=final_url if isinstance(final_url, str) else url,
            elapsed_ms=round((time.monotonic() - started) * 1000),
            status_code=status_code if isinstance(status_code, int) else None,
            network_requests=len(requests) if isinstance(requests, list) else connections,
            policy_denials=denials + len(blocked_resources),
        )
