"""Import a downloaded Open Facts sample; dry-run unless --apply is passed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import HistoricalPriceReference, Product, ProductOffer, ResearchImportRun, ResearchProduct
from app.services.research.openfacts_importer import DATASETS, MAX_IMPORT_COUNT, checksum, import_catalog


def database_engine():
    url = make_url(get_settings().database_url)
    if url.drivername.startswith("postgresql") and url.host == "localhost":
        url = url.set(host="127.0.0.1", query={**url.query, "connect_timeout": "5"})
    return create_engine(url, pool_pre_ping=True)


def counts(db: Session) -> dict[str, int]:
    return {
        "products": db.scalar(select(func.count(Product.id))) or 0,
        "research_products": db.scalar(select(func.count(ResearchProduct.id))) or 0,
        "research_import_runs": db.scalar(select(func.count(ResearchImportRun.id))) or 0,
        "offers": db.scalar(select(func.count(ProductOffer.id))) or 0,
        "historical_prices": db.scalar(select(func.count(HistoricalPriceReference.id))) or 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--flavor", choices=tuple(DATASETS), required=True)
    parser.add_argument("--limit", type=int, default=MAX_IMPORT_COUNT,
                        choices=range(1, MAX_IMPORT_COUNT + 1))
    parser.add_argument("--apply", action="store_true", help="commit additive Research records")
    args = parser.parse_args()
    if not args.input.is_file() or args.input.stat().st_size > 8 * 1024 * 1024:
        parser.error("input must be a local JSON file <=8 MiB")
    document = json.loads(args.input.read_text(encoding="utf-8"))
    source = DATASETS[args.flavor]
    if document.get("dataset_id") != source["id"]:
        parser.error("input dataset_id does not match --flavor")
    if document.get("source_homepage") != source["page"] or not document.get("source_url", "").startswith(source["api"] + "?"):
        parser.error("input source URL is not the official dataset API")
    if document.get("response_count") != len(document.get("products", [])):
        parser.error("manifest count does not match sample records")
    digest = checksum(args.input)
    revision = f"openfacts-{args.flavor}-{digest[:16]}"
    db_engine = database_engine()
    try:
        tables = set(inspect(db_engine).get_table_names())
        required = {"products", "research_products", "research_import_runs", "product_offers",
                    "historical_price_references"}
        if not required.issubset(tables):
            parser.error("database schema is incomplete; importer never creates or migrates tables")
        with Session(db_engine, autoflush=False, expire_on_commit=False) as db:
            before = counts(db)
            report = import_catalog(db, path=args.input, flavor=args.flavor, revision=revision,
                                    limit=min(args.limit, MAX_IMPORT_COUNT), dry_run=not args.apply)
            if report["imported"] > MAX_IMPORT_COUNT or report["offers_created"] or report["prices_created"]:
                raise RuntimeError("Research import safety invariant failed")
            if args.apply:
                db.flush()
                after = counts(db)
                expected = report["imported"]
                if (after["products"] - before["products"] != expected
                        or after["research_products"] - before["research_products"] != expected
                        or after["offers"] != before["offers"]
                        or after["historical_prices"] != before["historical_prices"]):
                    raise RuntimeError("Database count invariant failed; transaction rolled back")
                db.commit()
            else:
                after = before
                db.rollback()
            print(json.dumps({"status": "APPLIED" if args.apply else "DRY_RUN", "revision": revision,
                              "before": before, "after": after, "report": report}, ensure_ascii=False))
    finally:
        db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
