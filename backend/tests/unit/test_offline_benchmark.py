from pathlib import Path
from benchmarks.run import run


def test_offline_benchmark_reports_denominators_and_no_network():
    report, rows = run(Path(__file__).parents[2] / "benchmarks" / "fixtures.json")
    assert report["network_calls"] == 0
    assert report["crawl"]["name_accuracy"]["denominator"] == 3
    assert report["live"] == "N/A"
    assert len(rows) == 3
