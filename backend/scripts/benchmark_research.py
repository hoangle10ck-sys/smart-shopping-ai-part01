"""Reproducible real-catalog measurements; human-label metrics explicitly N/A."""
import argparse
import csv
from decimal import Decimal
import json
import math
from pathlib import Path
import statistics
import time
from collections import Counter

from app.core.database import SessionLocal
from app.services.research.recommendation import evaluate, parse_query
from scripts.download_research_metadata import REVISION
from app.services.research.importer import CATEGORIES


def budget_violated(price: str | None, lower: int | None, upper: int | None) -> bool:
    return price is None or (lower is not None and Decimal(price) < lower) or (upper is not None and Decimal(price) > upper)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/research"))
    parser.add_argument("--output", type=Path, default=Path("../docs/research-results"))
    parser.add_argument("--extra-data-dir", type=Path, action="append", default=[])
    parser.add_argument("--expansion-report", type=Path)
    args = parser.parse_args()
    verification = json.loads((args.output / "verification.json").read_text(encoding="utf-8"))
    assert verification["status"] == "RESEARCH_DATASET_VERIFIED"
    with Path("benchmarks/research_queries.csv").open(encoding="utf-8", newline="") as stream:
        queries = list(csv.DictReader(stream))
    constraints = json.loads(Path("benchmarks/research_constraint_cases.json").read_text(encoding="utf-8"))
    queries.extend(dict(id=c["id"], split="development", query=c["query"]) for c in constraints)
    expected = {c["id"]: c["expected"] for c in constraints}
    native = {}
    from app.services.research.importer import checksum
    for directory in [args.data_dir, *args.extra_data_dir]:
        for category in CATEGORIES:
            path = directory / f"meta_{category}.prefix.jsonl"
            manifest = json.loads(path.with_suffix(".manifest.json").read_text(encoding="utf-8"))
            assert checksum(path) == manifest["sha256"], "Benchmark input changed"
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                native[row["parent_asin"]] = row
    observations, latencies = [], []
    budget_n = violations = grounded = assertions = returned = 0
    parser_checks = []
    with SessionLocal() as db:
        from app.models import ResearchProduct, Product
        from sqlalchemy import select
        actual_catalog = {r.external_product_id: dict(input_sha256=r.input_sha256, record_sha256=r.record_sha256,
                          category=p.category) for r, p in db.execute(select(ResearchProduct, Product)
                          .join(Product, Product.id == ResearchProduct.product_id).where(ResearchProduct.revision == REVISION))}
        assert actual_catalog == verification["catalog_records"], "Catalog changed since verification"
        for query in queries:
            requirement = parse_query(query["query"])
            if query["id"] in expected:
                actual = requirement.model_dump()
                checks = {key: actual[key] == value for key, value in expected[query["id"]].items()}
                parser_checks.append(dict(id=query["id"], checks=checks, passed=all(checks.values())))
            times = []
            for _ in range(3):
                start = time.perf_counter()
                result, warnings = evaluate(db, requirement, revision=REVISION)
                times.append((time.perf_counter() - start) * 1000)
            latencies.extend(times)
            returned += len(result.recommendations)
            for item in result.recommendations:
                raw = native[item.research_provenance["parent_asin"]]
                # Independent direct native comparisons, not importer/scorer as oracle.
                checks = [item.name == raw["title"].strip(), item.rating == raw.get("average_rating"),
                          item.review_count == raw.get("rating_number")]
                if item.historical_price:
                    checks.append(Decimal(item.historical_price["amount"]) == Decimal(str(raw["price"])))
                grounded += sum(checks)
                assertions += len(checks)
                bounds = expected.get(query["id"], requirement.model_dump())
                low, high = bounds.get("budget_min"), bounds.get("budget_max")
                if bounds.get("currency", requirement.currency) == "USD" and (low is not None or high is not None):
                    budget_n += 1
                    violations += budget_violated(item.historical_price["amount"] if item.historical_price else None, low, high)
            observations.append(dict(id=query["id"], split=query["split"], query=query["query"],
                recommended=len(result.recommendations), eligible=result.total_filtered,
                latency_median_ms=round(statistics.median(times), 3),
                parent_asins=[i.research_provenance["parent_asin"] for i in result.recommendations]))
    imports = [json.loads((Path("research-artifacts") / f"import-{c}.json").read_text(encoding="utf-8")) for c in CATEGORIES]
    reimports = [json.loads((Path("research-artifacts") / f"reimport-{c}.json").read_text(encoding="utf-8")) for c in CATEGORIES]
    if args.expansion_report:
        expansion = json.loads(args.expansion_report.read_text(encoding="utf-8"))
        imports += expansion["first_imports"]
        reimports += expansion["repeat_imports"]
    missing = dict(value=None, numerator=None, denominator=0, reason="Independent human labels not available")
    report = dict(status="RESEARCH_BENCHMARK_MEASURED", live_crawl_success="NOT_APPLICABLE",
        revision=REVISION, prefix_hashes={key: value["sha256"] for key, value in verification["source_manifests"].items()},
        catalog_records=verification["catalog_records"], score_version="research-v1", parser_version="audit-v2",
        query_count=len(queries), split=dict(Counter(q["split"] for q in queries)), repeats=3,
        parser_contract_checks=parser_checks, parser_contract_origin="agent-authored regression expectations, NOT human relevance labels",
        metrics=dict(import_success=dict(numerator=sum(r["imported"] for r in imports),
                         denominator=sum(r["selected"] - r["duplicates"] for r in imports),
                         definition="new rows / selected nonduplicate identities; not raw-prefix yield"),
                     selection_yield=dict(numerator=sum(r["imported"] for r in imports), denominator=sum(r["scanned"] for r in imports),
                         definition="new rows / scanned prefix rows; includes intentional quota exclusions"),
                     duplicate_generated=dict(numerator=sum(r["imported"] for r in reimports), denominator=sum(r["selected"] for r in reimports)),
                     completeness=verification["completeness"],
                     budget_violations=dict(numerator=violations, denominator=budget_n),
                     source_field_support=dict(numerator=grounded, denominator=assertions, method="raw name/rating/review_count/historical price comparisons"),
                     returned_items=returned,
                     latency_ms=dict(p50=round(statistics.median(latencies), 3), p95=round(sorted(latencies)[math.ceil(.95*len(latencies))-1], 3), denominator=len(latencies)),
                     precision_at_5=missing, ndcg_at_5=missing, requirement_match_accuracy=missing,
                     semantic_explanation_grounding=missing), observations=observations)
    (args.output / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output / "benchmark.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(observations[0]))
        writer.writeheader()
        writer.writerows(observations)
    print(json.dumps(report["metrics"], ensure_ascii=True))


if __name__ == "__main__":
    main()
