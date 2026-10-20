"""Ingest approved phone/computer/headphone catalog data into the main DB."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict

from app.core.database import SessionLocal, init_db
from app.services.collectors.catalog_ingestion import (
    DEFAULT_CATALOG_QUERIES,
    CatalogIngestionService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch approved storefronts and idempotently upsert the catalog database."
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Storefront query; repeat to add categories. Defaults to phones, computers and headphones.",
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        default=[],
        help="Approved direct product URL; repeat for more URLs.",
    )
    return parser


async def run(args: argparse.Namespace) -> int:
    init_db()
    with SessionLocal() as db:
        summary = await CatalogIngestionService().ingest(
            db,
            queries=args.queries or list(DEFAULT_CATALOG_QUERIES),
            direct_urls=args.urls,
        )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 0 if not summary.failures else 2


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
