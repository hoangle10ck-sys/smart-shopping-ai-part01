from pathlib import Path

from benchmarks.llm_spec_ablation import run


def test_same_fixture_ablation_is_offline_and_has_explicit_denominators():
    report = run(Path(__file__).parents[2] / "benchmarks" / "llm_spec_fixtures.json")
    baseline = report["modes"]["without_llm"]
    guarded = report["modes"]["quote_verified_structured_output"]

    assert report["dataset_kind"] == "FIXTURE_TESTED_ONLY"
    assert baseline["network_calls"] == guarded["network_calls"] == 0
    assert baseline["expected"] == guarded["expected"] == 4
    assert baseline["recall"] == 0
    assert guarded["precision"] == 1
    assert guarded["recall"] == 0.75
