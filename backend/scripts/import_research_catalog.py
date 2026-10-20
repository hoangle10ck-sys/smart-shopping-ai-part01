"""Run from backend: python -m scripts.import_research_catalog --help."""
import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal, init_db
from app.services.research.importer import CATEGORIES, DATASET, import_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dataset", default=DATASET, choices=[DATASET])
    parser.add_argument("--revision", required=True)
    parser.add_argument("--category", choices=CATEGORIES, required=True)
    parser.add_argument("--limit", type=int, default=75)
    parser.add_argument("--category-quotas", type=json.loads, help='Mapped-category quotas, e.g. {"laptop": 17, "tai nghe": 17}')
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.report.resolve():
        parser.error("report must not overwrite input")
    init_db()
    with SessionLocal() as db:
        report = import_catalog(db, path=args.input, dataset=args.dataset, revision=args.revision,
                                category=args.category, limit=args.limit, dry_run=args.dry_run,
                                category_quotas=args.category_quotas)
        db.commit()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
