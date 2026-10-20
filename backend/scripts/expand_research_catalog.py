"""Add a bounded device-stratified cohort, preserving existing rows and snapshots."""
import argparse
import json
from pathlib import Path

from sqlalchemy import func, select
from app.core.database import SessionLocal, init_db
from app.models import ResearchProduct, HistoricalPriceReference, ProductOffer
from app.services.research.importer import checksum, import_catalog
from scripts.download_research_metadata import REVISION


def counts(db):
    return dict(products=db.scalar(select(func.count(ResearchProduct.id))),
                prices=db.scalar(select(func.count(HistoricalPriceReference.id))),
                research_offers=db.scalar(select(func.count(ProductOffer.id)).join(
                    ResearchProduct, ResearchProduct.product_id == ProductOffer.product_id)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/research-expanded"))
    parser.add_argument("--report", type=Path, default=Path("research-artifacts/expansion.json"))
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report exists; choose a new report path to preserve prior evidence")
    # Validate all inputs before any DB mutation.
    inputs = []
    for category, quotas in [("Electronics", {"laptop": 20, "tai nghe": 20}),
                             ("Cell_Phones_and_Accessories", {"dien thoai": 10})]:
        path = args.data_dir / f"meta_{category}.prefix.jsonl"
        manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        if manifest["sha256"] != checksum(path) or manifest["revision"] != REVISION:
            raise ValueError("Source manifest mismatch")
        inputs.append(dict(path=path, category=category, revision=REVISION, category_quotas=quotas, limit=50))
    init_db()
    with SessionLocal() as db:
        before = counts(db)
        first = [import_catalog(db, **kw) for kw in inputs]
        after = counts(db)
        if after["products"] > 200 or after["research_offers"] != before["research_offers"]:
            db.rollback()
            raise ValueError("Expansion exceeds bounded cohort or changes offers")
        db.commit()
        second = [import_catalog(db, **kw) for kw in inputs]
        repeated = counts(db)
        if repeated != after or any(r["imported"] for r in second):
            db.rollback()
            raise ValueError("Idempotency check failed")
        db.commit()
    report = dict(before=before, after=after, after_repeat=repeated, first_imports=first,
                  repeat_imports=second, selection="device quotas within official prefix; not random market coverage")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
