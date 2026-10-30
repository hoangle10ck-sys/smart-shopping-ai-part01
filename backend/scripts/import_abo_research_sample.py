"""Run from backend: python -m scripts.import_abo_research_sample [--apply]."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import HistoricalPriceReference, Product, ProductOffer, ResearchImportRun, ResearchProduct
from app.services.research.abo_importer import DATASET, MAX_IMPORT_COUNT, import_catalog


def database_engine():
    url = make_url(get_settings().database_url)
    # Compose publishes PostgreSQL on IPv4 loopback; avoid localhost resolving to ::1.
    if url.drivername.startswith("postgresql") and url.host == "localhost":
        url = url.set(host="127.0.0.1", query={**url.query, "connect_timeout": "5"})
    return create_engine(url, pool_pre_ping=True)


def counts(db: Session) -> dict[str, int]:
    return {
        "products": db.scalar(select(func.count(Product.id))) or 0,
        "research_products": db.scalar(select(func.count(ResearchProduct.id))) or 0,
        "research_import_runs": db.scalar(select(func.count(ResearchImportRun.id))) or 0,
        "product_offers": db.scalar(select(func.count(ProductOffer.id))) or 0,
        "historical_prices": db.scalar(select(func.count(HistoricalPriceReference.id))) or 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/research/abo/abo-balanced-200.jsonl"))
    parser.add_argument("--images", type=Path, default=Path("data/research/abo/images.csv.gz"))
    parser.add_argument("--manifest", type=Path, default=Path("data/research/abo/manifest.json"))
    parser.add_argument("--limit", type=int, default=MAX_IMPORT_COUNT, choices=range(1, MAX_IMPORT_COUNT + 1))
    parser.add_argument("--apply", action="store_true", help="commit additive research products; default is dry-run")
    args = parser.parse_args()
    if not (args.input.is_file() and args.images.is_file() and args.manifest.is_file()):
        parser.error("input catalog, image metadata, and manifest must exist")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("dataset_id") != DATASET or manifest.get("license") != "CC BY 4.0":
        parser.error("manifest is not the approved ABO CC BY 4.0 sample")
    if not 1 <= manifest.get("records_selected", 0) <= MAX_IMPORT_COUNT:
        parser.error("manifest record count exceeds the approved 200-record maximum")
    if manifest.get("catalog_sha256") != hashlib.sha256(args.input.read_bytes()).hexdigest():
        parser.error("catalog checksum does not match manifest")
    if manifest.get("images_metadata_sha256") != hashlib.sha256(args.images.read_bytes()).hexdigest():
        parser.error("image metadata checksum does not match manifest")
    revision = f"abo-cc-by-2021-{manifest['catalog_sha256'][:12]}"
    engine = database_engine()
    try:
        tables = set(inspect(engine).get_table_names())
        required = {"products", "research_products", "research_import_runs", "product_offers", "historical_price_references"}
        if not required.issubset(tables):
            parser.error("existing database schema is incomplete; importer will not create or migrate tables")
        with Session(engine, autoflush=False, expire_on_commit=False) as db:
            before = counts(db)
            report = import_catalog(
                db,
                path=args.input,
                image_metadata_path=args.images,
                revision=revision,
                limit=min(args.limit, manifest["records_selected"]),
                category_quotas=manifest.get("category_quotas"),
                dry_run=not args.apply,
            )
            if report["imported"] > MAX_IMPORT_COUNT or report["offers_created"] or report["prices_created"]:
                raise RuntimeError("import safety invariant failed")
            if args.apply:
                db.flush()
                after = counts(db)
                if (after["products"] - before["products"] != report["imported"]
                        or after["research_products"] - before["research_products"] != report["imported"]
                        or after["product_offers"] != before["product_offers"]
                        or after["historical_prices"] != before["historical_prices"]):
                    raise RuntimeError("database count invariants failed; transaction rolled back")
                db.commit()
            else:
                after = before
                db.rollback()
        print(json.dumps({
            "status": "APPLIED" if args.apply else "DRY_RUN",
            "revision": revision,
            "before": before,
            "after": after,
            "report": report,
        }, ensure_ascii=False))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
