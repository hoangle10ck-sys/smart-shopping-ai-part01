"""Read-only source/DB audit plus three persisted API journeys on the real catalog."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.core.database import SessionLocal, init_db
from app.main import app
from app.models import Product, ProductOffer, ResearchProduct, HistoricalPriceReference
from app.services.research.importer import CATEGORIES
from scripts.download_research_metadata import REVISION


def audit(data_dir: Path, extra_data_dirs: list[Path] | None = None) -> dict:
    source_lines, manifests = {}, {}
    for directory in [data_dir, *(extra_data_dirs or [])]:
        for category in CATEGORIES:
            path = directory / f"meta_{category}.prefix.jsonl"
            manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
            data = path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == manifest["sha256"], "Prefix checksum differs"
            assert manifest["revision"] == REVISION and manifest["range_status"] == 206
            source_lines[manifest["sha256"]] = data.splitlines(keepends=True)
            manifests[manifest["sha256"]] = manifest
    with SessionLocal() as db:
        rows = db.execute(select(Product, ResearchProduct, HistoricalPriceReference)
            .join(ResearchProduct, ResearchProduct.product_id == Product.id)
            .outerjoin(HistoricalPriceReference, HistoricalPriceReference.research_product_id == ResearchProduct.id)
            .where(ResearchProduct.revision == REVISION).order_by(ResearchProduct.external_product_id)).all()
        assert 100 <= len(rows) <= 200, "Expected bounded genuine research cohort"
        rng = random.Random(2023)
        checked = []
        for category in CATEGORIES:
            cohort = [row for row in rows if row[1].source_category == category]
            for product, research, ref in (cohort if extra_data_dirs else rng.sample(cohort, 10)):
                line = source_lines[research.input_sha256][research.line_number - 1]
                raw = json.loads(line)
                checks = dict(identity=research.external_product_id == raw["parent_asin"],
                    name=product.name == raw["title"].strip(),
                    rating=product.rating == raw.get("average_rating"),
                    review_count=product.review_count == raw.get("rating_number"),
                    record_hash=research.record_sha256 == hashlib.sha256(line).hexdigest(),
                    input_hash=research.input_sha256 in manifests,
                    brand=product.brand == (raw.get("details") or {}).get("Brand"),
                    price=(ref is None and raw.get("price") in (None, "None", "")) or
                          (ref is not None and Decimal(ref.amount) == Decimal(str(raw["price"])) and
                           ref.currency == "USD" and ref.price_observed_at is None))
                assert all(checks.values()), (research.external_product_id, checks)
                checked.append(dict(parent_asin=research.external_product_id, category=category,
                                    line=research.line_number, checks=checks))
        offer_count = db.scalar(select(func.count(ProductOffer.id)).where(ProductOffer.product_id.in_([p.id for p, _, _ in rows])))
        assert offer_count == 0
        completeness = {field: {"numerator": sum(getattr(p, field) is not None for p, _, _ in rows), "denominator": len(rows)}
                        for field in ("name", "category", "brand", "model", "rating", "review_count", "image_url")}
        prices = sum(ref is not None for _, _, ref in rows)
        completeness["historical_price_USD"] = dict(numerator=prices, denominator=len(rows))
        report = dict(status="RESEARCH_DATASET_VERIFIED", live_status="LIVE_NOT_VERIFIED",
            revision=REVISION, source_manifests=manifests, product_count=len(rows), price_reference_count=prices,
            offer_count=offer_count, completeness=completeness,
            source_category_counts=dict(Counter(r.source_category for _, r, _ in rows)),
            mapped_category_counts=dict(Counter(p.category for p, _, _ in rows)),
            independent_raw_checks=checked, audit_method="all records" if extra_data_dirs else "20 seeded records; direct raw comparisons without importer mapping",
            catalog_records={r.external_product_id: dict(input_sha256=r.input_sha256, record_sha256=r.record_sha256,
                category=p.category) for p, r, _ in rows},
            price_unknown=len(rows)-prices)
    client = TestClient(app)
    journeys = []
    for query in ["phụ kiện điện thoại dưới 50 USD", "điện tử", "điện thoại RAM 999GB"]:
        response = client.post("/api/research/search", json={"raw_query": query, "revision": REVISION})
        assert response.status_code == 200, response.text
        result = response.json()
        sid = result["session_id"]
        items = result["recommendations"]
        assert client.get(f"/api/search/{sid}").json()["recommendations"] == items
        assert client.get(f"/api/history/{sid}").json()["result"]["recommendations"] == items
        comparison_id = None
        if len(items) >= 2:
            comparison = client.post("/api/comparisons", json={"session_id": sid, "product_ids": [i["product_id"] for i in items[:2]]})
            assert comparison.status_code == 201, comparison.text
            comparison_id = comparison.json()["id"]
            assert all(p["best_offer"] is None for p in comparison.json()["result"]["products"])
        for item in items:
            assert item["offer_id"] is None and item["price"] is None
            detail = client.get(f"/api/products/{item['product_id']}?session_id={sid}")
            assert detail.status_code == 200 and detail.json()["offers"] == []
        journeys.append(dict(query=query, session_id=sid, recommendations=len(items), comparison_id=comparison_id,
            parent_asins=[i["research_provenance"]["parent_asin"] for i in items], latency_ms=result["processing_time_ms"]))
    assert journeys[0]["recommendations"] >= 2 and journeys[1]["recommendations"] >= 2
    assert journeys[2]["recommendations"] == 0
    report["api_journeys"] = journeys
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/research"))
    parser.add_argument("--report", type=Path, default=Path("../docs/research-results/verification.json"))
    parser.add_argument("--extra-data-dir", type=Path, action="append", default=[])
    args = parser.parse_args()
    init_db()
    report = audit(args.data_dir, args.extra_data_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"source_manifests", "independent_raw_checks", "catalog_records"}}, ensure_ascii=True))


if __name__ == "__main__":
    main()
