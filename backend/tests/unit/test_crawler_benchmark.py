import json

from scripts.crawler_benchmark import compute_report, run


def test_crawler_benchmark_reports_denominators_by_source_and_no_network():
    dataset = {
        "dataset": "tiny-manual-fixture",
        "kind": "UNIT_TEST_ONLY",
        "records": [
            {
                "source_id": "source-a",
                "url": "https://store.example/p/1",
                "status": "SUCCESS",
                "product_page_verified": True,
                "truth": {"name": "Phone", "price": 123, "sku": "A1", "product_key": "phone"},
                "observed": {
                    "name": "Phone",
                    "price": 123,
                    "sku": "A1",
                    "price_evidence": True,
                    "saved": True,
                    "dedup_key": "phone-1",
                    "freshness_status": "FRESH",
                },
                "latency_ms": 10,
            },
            {
                "source_id": "source-a",
                "url": "https://store.example/p/2",
                "status": "SUCCESS",
                "product_page_verified": True,
                "truth": {"name": "Phone", "price": 123, "sku": "A1", "product_key": "phone"},
                "observed": {
                    "name": "Phone",
                    "price": 123,
                    "sku": "A1",
                    "price_evidence": True,
                    "saved": True,
                    "dedup_key": "phone-1",
                    "freshness_status": "FRESH",
                },
                "latency_ms": 20,
            },
            {
                "source_id": "source-a",
                "url": "https://store.example/p/3",
                "status": "ACCESS_RESTRICTED",
                "product_page_verified": False,
                "truth": {"name": "Phone", "price": 123, "sku": "A1", "product_key": "phone"},
                "observed": {
                    "name": None,
                    "price": None,
                    "sku": None,
                    "dedup_key": None,
                    "freshness_status": "UNKNOWN",
                },
                "latency_ms": 30,
            },
        ],
    }

    report, rows = compute_report(dataset)

    assert report["network_calls"] == 0
    assert report["sample_count"] == 3
    assert report["metrics"]["fetch_success_rate"] == {
        "numerator": 2, "denominator": 3, "value": 2 / 3
    }
    assert report["metrics"]["field_precision_by_name_price_sku"]["price"] == {
        "numerator": 2, "denominator": 2, "value": 1.0
    }
    assert report["metrics"]["price_evidence_coverage"]["value"] == 1.0
    assert report["metrics"]["completeness"]["value"] == 1.0
    assert report["metrics"]["dedup_precision"] == {
        "numerator": 1, "denominator": 1, "value": 1.0
    }
    assert report["metrics"]["save_success_rate"]["value"] == 1.0
    assert report["metrics"]["restricted_urls"] == 1
    assert report["metrics"]["latency_ms"]["p50"] == 20
    assert report["by_source"]["source-a"]["attempted"] == 3
    assert rows[0]["price_correct"] is True


def test_crawler_benchmark_uses_null_for_undefined_ratios():
    report, _ = compute_report(
        {"dataset": "empty", "records": []}
    )

    assert report["metrics"]["fetch_success_rate"]["value"] is None
    assert report["metrics"]["dedup_precision"]["value"] is None
    assert report["metrics"]["save_success_rate"]["value"] is None


def test_crawler_benchmark_exports_csv_and_json(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            {
                "dataset": "export-test",
                "records": [
                    {
                        "source_id": "source-a",
                        "url": "https://user:password@store.example/item?token=secret",
                        "status": "FETCH_ERROR",
                        "truth": {},
                        "observed": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "reports"

    report = run(dataset_path, output_path)

    assert report["network_calls"] == 0
    assert json.loads((output_path / "report.json").read_text(encoding="utf-8"))[
        "sample_count"
    ] == 1
    assert (output_path / "records.csv").read_text(encoding="utf-8").startswith(
        "source_id,url,attempted_at,status"
    )
    assert "password" not in (output_path / "records.csv").read_text(
        encoding="utf-8"
    )
    assert "token=secret" not in (output_path / "records.csv").read_text(
        encoding="utf-8"
    )
