"""Metric arithmetic uses synthetic judgments, never real benchmark claims."""
import csv
import math

import pytest

from app.services.research.evaluation import ranking_metrics
from scripts.evaluate_research_labels import FIELDS, load_labels


@pytest.mark.parametrize("price,lower,upper,violated", [
    ("7.98", 20, 50, True), ("20.00", 20, 50, False),
    ("50.00", 20, 50, False), ("50.01", 20, 50, True),
    (None, 20, None, True), ("200.00", 200, None, False),
])
def test_benchmark_checks_both_budget_bounds(price, lower, upper, violated):
    from scripts.benchmark_research import budget_violated
    assert budget_violated(price, lower, upper) is violated


def test_precision_fixed_k_and_discounted_gain():
    observations = [dict(id="q", split="evaluation", parent_asins=["b", "a"])]
    report = ranking_metrics(observations, {("q", "a"): 3, ("q", "b"): 1}, {"a", "b"})
    assert report["precision_at_k"]["value"] == .2
    expected = (1 + 7 / math.log2(3)) / (7 + 1 / math.log2(3))
    assert report["ndcg_at_k"]["value"] == pytest.approx(expected)


def test_unjudged_is_not_assumed_irrelevant_and_development_excluded():
    obs = [dict(id="q", split="evaluation", parent_asins=["a"]), dict(id="dev", split="development", parent_asins=["a"])]
    report = ranking_metrics(obs, {("q", "a"): 3}, {"a", "b"})
    assert report["precision_at_k"]["value"] is None
    assert report["incomplete_queries"] == ["q"]


def test_no_relevant_ground_truth_keeps_ndcg_undefined():
    report = ranking_metrics([dict(id="q", split="evaluation", parent_asins=[])], {("q", "a"): 0}, {"a"})
    assert report["precision_at_k"]["value"] == 0
    assert report["ndcg_at_k"]["value"] is None
    assert report["zero_ideal_gain_queries"] == ["q"]


@pytest.mark.parametrize("bad", [["a", "a"], ["unknown"]])
def test_rank_integrity(bad):
    with pytest.raises(ValueError):
        ranking_metrics([dict(id="q", split="evaluation", parent_asins=bad)], {("q", "a"): 3}, {"a"})


def test_blank_template_and_provenance_validation(tmp_path):
    row = {field: "" for field in FIELDS}
    row.update(query_id="q", query="fixture", parent_asin="a", revision="test", input_sha256="hash", line_number="1")
    expected = {("q", "a"): dict(row)}
    path = tmp_path / "labels.csv"
    def write():
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(row)
    write()
    assert load_labels(path, expected) == {}
    row["relevance"] = "3"
    write()
    with pytest.raises(ValueError, match="reviewer"):
        load_labels(path, expected)
    row.update(reviewer="synthetic-test", reviewed_at="test", evidence="fixture", adjudication="test")
    write()
    assert load_labels(path, expected) == {("q", "a"): 3}
    row["revision"] = "wrong"
    write()
    with pytest.raises(ValueError, match="provenance"):
        load_labels(path, expected)
