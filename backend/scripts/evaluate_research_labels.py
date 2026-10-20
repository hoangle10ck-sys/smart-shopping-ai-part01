"""Export blank judgments or score supplied adjudicated labels without changing catalog."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import ResearchProduct
from app.services.research.evaluation import ranking_metrics

FIELDS = ["query_id", "query", "parent_asin", "revision", "source_category", "line_number",
          "input_sha256", "relevance", "reviewer", "reviewed_at", "evidence", "adjudication"]


def load_labels(path: Path, expected: dict[tuple[str, str], dict]) -> dict:
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Label file exceeds 10 MiB")
    result = {}
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS) <= set(reader.fieldnames or []):
            raise ValueError("Missing label columns; start from template")
        for row in reader:
            key = row["query_id"], row["parent_asin"]
            if key in seen or key not in expected:
                raise ValueError("Duplicate/unknown query-product judgment")
            seen.add(key)
            for field in ("revision", "input_sha256", "source_category", "line_number", "query"):
                if row[field] != str(expected[key][field]):
                    raise ValueError(f"Judgment provenance mismatch: {field}")
            if not row["relevance"].strip():
                continue
            if row["relevance"] not in {"0", "1", "2", "3"}:
                raise ValueError("Relevance must be an integer 0..3")
            if any(not row[field].strip() for field in ("reviewer", "reviewed_at", "evidence", "adjudication")):
                raise ValueError("Completed judgment requires reviewer/date/evidence/adjudication")
            result[key] = int(row["relevance"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["template", "score"])
    parser.add_argument("--benchmark", type=Path, default=Path("../docs/research-results/benchmark.json"))
    parser.add_argument("--labels", type=Path, default=Path("research-artifacts/relevance-labels.csv"))
    parser.add_argument("--output", type=Path, default=Path("research-artifacts/human-ranking.json"))
    args = parser.parse_args()
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        catalog = list(db.scalars(select(ResearchProduct).where(ResearchProduct.revision == benchmark["revision"])
                                  .order_by(ResearchProduct.external_product_id)))
        if not catalog:
            raise ValueError("No catalog for benchmark revision")
        frozen = benchmark.get("catalog_records")
        if frozen is not None and set(frozen) != {item.external_product_id for item in catalog}:
            raise ValueError("Catalog membership differs from benchmark")
        expected = {}
        for query in benchmark["observations"]:
            if query["split"] != "evaluation":
                continue
            for item in catalog:
                if frozen is not None:
                    record = frozen[item.external_product_id]
                    if record["input_sha256"] != item.input_sha256 or record["record_sha256"] != item.record_sha256:
                        raise ValueError("Catalog record differs from benchmark")
                elif benchmark["prefix_hashes"].get(item.source_category) != item.input_sha256:
                    raise ValueError("Catalog prefix differs from benchmark")
                expected[(query["id"], item.external_product_id)] = dict(query_id=query["id"], query=query["query"],
                    parent_asin=item.external_product_id, revision=item.revision, source_category=item.source_category,
                    line_number=item.line_number, input_sha256=item.input_sha256,
                    relevance="", reviewer="", reviewed_at="", evidence="", adjudication="")
    if args.action == "template":
        args.labels.parent.mkdir(parents=True, exist_ok=True)
        with args.labels.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(expected.values())
        print(f"Exported {len(expected)} BLANK judgments; no ranks, scores or inferred labels.")
        return
    if args.output.resolve() in {args.labels.resolve(), args.benchmark.resolve()}:
        raise ValueError("Output cannot overwrite labels or benchmark")
    judgments = load_labels(args.labels, expected)
    report = dict(status="LABELS_PENDING" if not judgments else "SUPPLIED_LABELS_SCORED",
        label_origin="operator-supplied; software cannot certify independent human authorship",
        label_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(), revision=benchmark["revision"],
        prefix_hashes=benchmark["prefix_hashes"], judgments=len(judgments),
        metrics=ranking_metrics(benchmark["observations"], judgments, {r.external_product_id for r in catalog}))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
