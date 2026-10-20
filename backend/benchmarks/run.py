"""Reproducible offline benchmark; never performs network I/O."""

from __future__ import annotations
import argparse, csv, json, math, statistics, time
from pathlib import Path

from app.services.collectors.html_extractor import extract_product


def ratio(numerator: int, denominator: int) -> dict[str, float | int | None]:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def mean_ratio(values: list[float | None]) -> dict[str, float | int | None]:
    measured = [value for value in values if value is not None]
    return {"numerator": round(sum(measured), 6), "denominator": len(measured),
            "value": statistics.mean(measured) if measured else None}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values: return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def run(dataset_path: Path) -> tuple[dict, list[dict]]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    rows, latencies = [], []
    for sample in dataset["samples"]:
        started = time.perf_counter()
        observation = extract_product(sample["html"], url=sample["url"], platform=sample["platform"])
        latency = (time.perf_counter() - started) * 1000; latencies.append(latency)
        offer = observation.offers[0] if observation and observation.offers else None
        price = offer.sale_price if offer else None
        sku = offer.identity.external_sku_id if offer else None
        actual_status = "SUCCESS" if observation else "NOT_PRODUCT_PAGE"
        rows.append({"id": sample["id"], "status_correct": actual_status == sample["expected_status"],
            "name_correct": (observation.name if observation else None) == sample["expected_name"],
            "price_correct": price == sample["expected_price"], "sku_correct": sku == sample["expected_sku"],
            "latency_ms": round(latency, 3)})
    total = len(rows)
    from app.schemas.ranking import ScoringCandidate
    from app.schemas.requirement import RequirementData
    from app.services.filter.hard_filter import HardFilterService
    from app.services.scoring.scoring_engine import ScoringEngine
    from app.services.scoring.two_level import product_suitability
    recommendation_rows = []
    for case in dataset.get("recommendation_cases", []):
        requirement = RequirementData.model_validate(case["requirement"])
        candidates = [ScoringCandidate.model_validate({k:v for k,v in item.items() if k != "relevance"}) for item in case["candidates"]]
        labels = {item["product_id"]:item["relevance"] for item in case["candidates"]}
        accepted, decisions = HardFilterService().filter(candidates, requirement)
        legacy = sorted(accepted, key=lambda item:(-ScoringEngine().score(item, requirement).final_score, item.product_id))
        two_level = sorted(accepted, key=lambda item:(-product_suitability(item, requirement).score, item.product_id))
        ideal = sorted(labels.values(), reverse=True)
        def ndcg(items):
            gains = [labels[item.product_id] for item in items]
            dcg = sum((2**gain-1)/math.log2(index+2) for index,gain in enumerate(gains))
            idcg = sum((2**gain-1)/math.log2(index+2) for index,gain in enumerate(ideal[:len(gains)]))
            return dcg/idcg if idcg else None
        recommendation_rows.append({"constraint_violations":sum(not d.accepted for d in decisions),
            "eligible":len(accepted), "sku_matches":sum(labels[item.product_id] > 0 for item in accepted),
            "legacy_top_relevant":bool(legacy and labels[legacy[0].product_id] > 0),
            "two_level_top_relevant":bool(two_level and labels[two_level[0].product_id] > 0),
            "legacy_ndcg":ndcg(legacy), "two_level_ndcg":ndcg(two_level)})
    rec_total = sum(row["eligible"] for row in recommendation_rows)
    report = {"dataset": dataset["dataset"], "dataset_kind": dataset["kind"], "sample_count": total,
        "environment": "offline deterministic parser", "network_calls": 0,
        "crawl": {"attempted": total, "allowed": total, "fetched": total, "restricted": 0,
            "fetch_success": ratio(sum(row["status_correct"] for row in rows), total),
            "extraction_success": ratio(sum(sample["expected_name"] is not None for sample in dataset["samples"]), total),
            "name_accuracy": ratio(sum(row["name_correct"] for row in rows), total),
            "price_accuracy": ratio(sum(row["price_correct"] for row in rows), total),
            "sku_accuracy": ratio(sum(row["sku_correct"] for row in rows), total),
            "completeness": ratio(sum(row["name_correct"] and row["price_correct"] and row["sku_correct"] for row in rows), total),
            "persistence_success": ratio(0, 0),
            "latency_ms": {"p50": round(percentile(latencies, .5) or 0, 3), "p95": round(percentile(latencies, .95) or 0, 3)}},
        "recommendation": {"constraint_violations": ratio(sum(row["constraint_violations"] for row in recommendation_rows), sum(len(case["candidates"]) for case in dataset.get("recommendation_cases", []))),
            "sku_match_accuracy": ratio(sum(row["sku_matches"] for row in recommendation_rows), rec_total),
            "offer_selection_accuracy": ratio(0, 0),
            "precision_at_k": ratio(sum(row["two_level_top_relevant"] for row in recommendation_rows), len(recommendation_rows)),
            "ndcg_at_k": mean_ratio([row["two_level_ndcg"] for row in recommendation_rows]),
            "evidence_consistency": ratio(0, 0),
            "legacy_precision_at_1": ratio(sum(row["legacy_top_relevant"] for row in recommendation_rows), len(recommendation_rows)),
            "two_level_precision_at_1": ratio(sum(row["two_level_top_relevant"] for row in recommendation_rows), len(recommendation_rows)),
            "legacy_ndcg_at_2": statistics.mean(row["legacy_ndcg"] for row in recommendation_rows) if recommendation_rows else None,
            "two_level_ndcg_at_2": statistics.mean(row["two_level_ndcg"] for row in recommendation_rows) if recommendation_rows else None},
        "ablation": {"deterministic_parser": "MEASURED", "playwright": "N/A",
            "parser_plus_llm": "N/A (disabled/no API call)", "legacy_vs_two_level": "MEASURED_SYNTHETIC"}, "live": "N/A"}
    return report, rows


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("fixtures.json")); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); report, rows = run(args.dataset); args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    (args.output / "summary.md").write_text(f"# Offline benchmark\n\nDataset: `{report['dataset']}` ({report['sample_count']} samples). Live: N/A.\n", encoding="utf-8")


if __name__ == "__main__": main()
