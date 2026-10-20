"""Offline same-fixture ablation of no-LLM vs quote-verified structured output."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.services.extraction.llm_spec_fallback import SpecExtraction


def score(predicted: dict[str, str], expected: dict[str, str]) -> dict:
    correct = sum(predicted.get(key) == value for key, value in expected.items())
    return {
        "correct": correct,
        "predicted": len(predicted),
        "expected": len(expected),
        "precision": correct / len(predicted) if predicted else None,
        "recall": correct / len(expected) if expected else None,
    }


def verified_output(text: str, payload: dict) -> dict[str, str]:
    extraction = SpecExtraction.model_validate(payload)
    folded = text.casefold()
    return {
        key: item.value
        for key, item in extraction.specifications.items()
        if item.quote.casefold() in folded
    }


def run(dataset_path: Path) -> dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    modes = {"without_llm": [], "quote_verified_structured_output": []}
    for sample in dataset["samples"]:
        started = time.perf_counter()
        baseline = {}
        baseline_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        guarded = verified_output(sample["text"], sample["model_output"])
        guarded_ms = (time.perf_counter() - started) * 1000
        modes["without_llm"].append({**score(baseline, sample["expected"]), "latency_ms": baseline_ms})
        modes["quote_verified_structured_output"].append({**score(guarded, sample["expected"]), "latency_ms": guarded_ms})

    def aggregate(rows):
        correct = sum(row["correct"] for row in rows)
        predicted = sum(row["predicted"] for row in rows)
        expected = sum(row["expected"] for row in rows)
        return {
            "correct": correct,
            "predicted": predicted,
            "expected": expected,
            "precision": correct / predicted if predicted else None,
            "recall": correct / expected if expected else None,
            "latency_ms_total": sum(row["latency_ms"] for row in rows),
            "network_calls": 0,
            "estimated_cost": 0,
        }

    return {
        "dataset": dataset["dataset"],
        "dataset_kind": dataset["kind"],
        "sample_count": len(dataset["samples"]),
        "modes": {name: aggregate(rows) for name, rows in modes.items()},
        "limitations": [
            "Structured outputs are checked-in simulated model responses, not a paid-provider measurement.",
            "Latency measures local schema and quote validation only.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path,
        default=Path(__file__).with_name("llm_spec_fixtures.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
