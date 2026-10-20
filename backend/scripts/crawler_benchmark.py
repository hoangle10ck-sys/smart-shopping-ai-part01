"""Evaluate a manually labelled crawler dataset without network access."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SUCCESS_STATUSES = {"SUCCESS", "PARTIAL_DATA"}
RESTRICTED_STATUSES = {"ACCESS_RESTRICTED", "ROBOTS_DISALLOWED", "SOURCE_NOT_PERMITTED"}
FIELDS = ("name", "price", "sku")


def ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def _safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return "[redacted-invalid-url]"
    if not parsed.scheme or not host:
        return "[redacted-invalid-url]"
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _metric_rows(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    fetch_success = sum(item["status"] in SUCCESS_STATUSES for item in records)
    product_pages = [
        item for item in records if item.get("product_page_verified") is True
    ]
    field_metrics: dict[str, dict[str, int | float | None]] = {}
    expected_field_count = 0
    correct_expected_fields = 0
    for field in FIELDS:
        predicted = [
            item for item in records
            if item.get("observed", {}).get(field) is not None
        ]
        correct = sum(
            item.get("truth", {}).get(field) is not None
            and item["observed"][field] == item["truth"][field]
            for item in predicted
        )
        truth_available = sum(
            item.get("truth", {}).get(field) is not None for item in product_pages
        )
        expected_field_count += truth_available
        correct_expected_fields += sum(
            item.get("truth", {}).get(field) is not None
            and item.get("observed", {}).get(field) == item["truth"][field]
            for item in product_pages
        )
        field_metrics[field] = ratio(correct, len(predicted))

    prices = [
        item for item in records if item.get("observed", {}).get("price") is not None
    ]
    evidence_coverage = sum(
        item.get("observed", {}).get("price_evidence") is True for item in prices
    )
    save_eligible = product_pages
    saved = sum(item.get("observed", {}).get("saved") is True for item in save_eligible)

    duplicate_pairs = 0
    correct_duplicate_pairs = 0
    observed_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        key = item.get("observed", {}).get("dedup_key")
        if key is not None:
            observed_groups[str(key)].append(item)
    for group in observed_groups.values():
        for left, right in itertools.combinations(group, 2):
            duplicate_pairs += 1
            left_truth = left.get("truth", {}).get("product_key")
            right_truth = right.get("truth", {}).get("product_key")
            if left_truth is not None and left_truth == right_truth:
                correct_duplicate_pairs += 1

    latencies = [
        float(item["latency_ms"])
        for item in records
        if item.get("latency_ms") is not None
    ]
    return {
        "attempted": total,
        "fetch_success_rate": ratio(fetch_success, total),
        "product_page_verified_rate": ratio(len(product_pages), total),
        "field_precision_by_name_price_sku": field_metrics,
        "price_evidence_coverage": ratio(evidence_coverage, len(prices)),
        "completeness": ratio(correct_expected_fields, expected_field_count),
        "dedup_precision": ratio(correct_duplicate_pairs, duplicate_pairs),
        "save_success_rate": ratio(saved, len(save_eligible)),
        "restricted_urls": sum(item["status"] in RESTRICTED_STATUSES for item in records),
        "unknown_urls": sum(item["status"] in {"FETCH_ERROR", "INVALID_URL", "NOT_TESTED_LIVE"} for item in records),
        "stale_urls": sum(
            item.get("observed", {}).get("freshness_status") == "STALE"
            for item in records
        ),
        "latency_ms": {
            "sample_count": len(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
        },
    }


def compute_report(dataset: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(dataset.get("dataset"), str) or not dataset["dataset"].strip():
        raise ValueError("dataset must have a non-empty dataset name")
    records = dataset.get("records")
    if not isinstance(records, list):
        raise ValueError("dataset records must be an array")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"records[{index}] must be an object")
        if not isinstance(record.get("source_id"), str) or not record["source_id"]:
            raise ValueError(f"records[{index}].source_id is required")
        if not isinstance(record.get("url"), str) or not record["url"]:
            raise ValueError(f"records[{index}].url is required")
        if not isinstance(record.get("status"), str):
            raise ValueError(f"records[{index}].status is required")
        if not isinstance(record.get("truth", {}), dict) or not isinstance(
            record.get("observed", {}), dict
        ):
            raise ValueError(f"records[{index}] truth and observed must be objects")

    by_source = {
        source: _metric_rows([row for row in records if row["source_id"] == source])
        for source in sorted({row["source_id"] for row in records})
    }
    report = {
        "dataset": dataset["dataset"],
        "dataset_kind": dataset.get("kind", "UNSPECIFIED"),
        "network_calls": 0,
        "sample_count": len(records),
        "metrics": _metric_rows(records),
        "by_source": by_source,
        "limitations": dataset.get("limitations", []),
    }
    rows = [
        {
            "source_id": item["source_id"],
            "url": _safe_url(item["url"]),
            "attempted_at": item.get("attempted_at"),
            "status": item["status"],
            "product_page_verified": item.get("product_page_verified", False),
            **{
                f"{field}_correct": (
                    item.get("truth", {}).get(field) is not None
                    and item.get("observed", {}).get(field) == item["truth"][field]
                )
                for field in FIELDS
            },
            "price_evidence": item.get("observed", {}).get("price_evidence", False),
            "saved": item.get("observed", {}).get("saved", False),
            "dedup_key": item.get("observed", {}).get("dedup_key"),
            "freshness_status": item.get("observed", {}).get("freshness_status"),
            "latency_ms": item.get("latency_ms"),
        }
        for item in records
    ]
    return report, rows


def run(dataset_path: Path, output_path: Path) -> dict[str, Any]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    report, rows = compute_report(dataset)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = list(rows[0]) if rows else [
        "source_id", "url", "attempted_at", "status", "product_page_verified",
        "name_correct", "price_correct", "sku_correct", "price_evidence",
        "saved", "dedup_key", "freshness_status", "latency_ms",
    ]
    with (output_path / "records.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_path / "summary.md").write_text(
        f"# Crawler benchmark\n\n"
        f"- Dataset: `{report['dataset']}` (`{report['dataset_kind']}`)\n"
        f"- Records: {report['sample_count']}\n"
        f"- Network calls: {report['network_calls']}\n"
        f"- Live status: not inferred by this offline evaluator\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.dataset, args.output)


if __name__ == "__main__":
    main()
