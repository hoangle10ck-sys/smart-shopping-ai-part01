"""Operator CLI for approved-source preflight and bounded Live ingestion."""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
from dataclasses import asdict

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.schemas.collector import FetchStatus
from app.services.collectors.catalog_ingestion import CatalogIngestionService, DEFAULT_CATALOG_QUERIES
from app.services.collectors.network_policy import build_pinned_http_client
from app.services.collectors.preflight import preflight_source
from app.services.collectors.service import CollectorService
from app.services.collectors.source_registry import SourceRegistry


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight", help="Check registration, DNS, terms metadata and robots.")
    check.add_argument("--url", required=True)
    ingest = commands.add_parser("ingest", help="Fetch and persist a bounded approved catalog.")
    ingest.add_argument("--live", action="store_true", help="Required acknowledgement for network collection.")
    ingest.add_argument("--url", action="append", default=[])
    ingest.add_argument("--query", action="append")
    ingest.add_argument("--max-products", type=int, default=5, choices=range(1, 6), metavar="1..5")
    ingest.add_argument("--max-pages", type=int, default=2, choices=range(1, 3), metavar="1..2")
    return root


def bounded_registry(registry: SourceRegistry, max_products: int, max_pages: int) -> SourceRegistry:
    return SourceRegistry([
        source.model_copy(update={
            "max_products": min(source.max_products, max_products),
            "max_pages": min(source.max_pages, max_pages),
        })
        for source in registry.enabled()
    ])


async def run_preflight(url: str) -> tuple[int, dict]:
    settings = get_settings()
    registry = SourceRegistry.from_json(settings.collector_source_registry_json)
    source = registry.resolve_url(url)
    if source is None:
        return 2, {
            "status": FetchStatus.SOURCE_NOT_PERMITTED.value,
            "url": url,
            "message": "URL is not in COLLECTOR_SOURCE_REGISTRY_JSON.",
        }
    async with build_pinned_http_client(
        allowed_domains=[source.domain],
        allow_subdomains=source.allow_subdomains,
        resolver=socket.getaddrinfo,
        timeout=settings.collector_http_timeout_seconds,
    ) as client:
        result = await preflight_source(
            url,
            source,
            client,
            resolver=socket.getaddrinfo,
            min_interval_seconds=settings.collector_min_interval_seconds,
        )
    payload = {
        "status": "ALLOWED" if result.allowed else (result.status or FetchStatus.SOURCE_NOT_PERMITTED).value,
        "url": result.canonical_url or url,
        "source_id": source.source_id,
        "permission_status": source.permission_status,
        "terms_checked_at": source.terms_checked_at.isoformat() if source.terms_checked_at else None,
        "robots_checked_at": result.robots_checked_at.isoformat() if result.robots_checked_at else None,
        "message": result.message,
    }
    return (0 if result.allowed else 2), payload


async def run_ingest(args: argparse.Namespace) -> tuple[int, dict]:
    if not args.live:
        return 2, {
            "status": "LIVE_ACK_REQUIRED",
            "message": "Pass --live only after source permission and policy review are confirmed.",
        }
    settings = get_settings()
    if not (settings.collector_live_enabled and settings.collector_policy_confirmed):
        return 2, {
            "status": FetchStatus.SOURCE_NOT_PERMITTED.value,
            "message": "COLLECTOR_LIVE_ENABLED and COLLECTOR_POLICY_CONFIRMED must both be true.",
        }
    registry = bounded_registry(
        SourceRegistry.from_json(settings.collector_source_registry_json),
        args.max_products,
        args.max_pages,
    )
    collector = CollectorService(enabled=True, registry=registry)
    init_db()
    with SessionLocal() as db:
        summary = await CatalogIngestionService(collector=collector).ingest(
            db,
            queries=args.query or list(DEFAULT_CATALOG_QUERIES),
            direct_urls=args.url,
        )
    payload = asdict(summary)
    payload["status"] = "COMPLETED" if summary.persisted else "NO_RECORDS_SAVED"
    return (0 if summary.persisted and not summary.failures else 2), payload


async def async_main(args: argparse.Namespace) -> int:
    if args.command == "preflight":
        code, payload = await run_preflight(args.url)
    else:
        code, payload = await run_ingest(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def main() -> int:
    return asyncio.run(async_main(parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
