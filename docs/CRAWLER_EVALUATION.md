# Crawler evaluation

## Result summary

| Measure | Result | Evidence / limitation |
|---|---:|---|
| Approved merchant sources | 0 | No merchant-specific permission basis established; see [source matrix](CRAWLER_SOURCE_MATRIX.md). |
| Real product URLs fetched | 0 | No live product-page or storefront product request was made. |
| Verified products / offers saved from Live | 0 / 0 | No Live observation exists. |
| Live fetch success, field precision, price coverage, completeness | N/A | No Live ground-truth dataset. |
| Live dedup precision, save success, restricted/unknown/stale counts | N/A | No Live ingestion run. |
| Live p50/p95 latency | N/A | No Live request timing was collected. |
| Full backend suite | 938 passed | Final 2026-10-16 regression after transport/browser changes; exact command is in `CRAWLER_PROGRESS.md`. |
| Frontend validation | 44 tests, lint/build pass; 15 E2E pass | No Live product network calls. |
| Synthetic parser benchmark samples | 3 | `backend/benchmarks/fixtures.json`; explicitly `FIXTURE_TESTED_ONLY`. |
| Crawl4AI runtime smoke | 1/1 success | Permitted scraping sandbox only: HTTP 200, JS DOM found, 8,985 bytes, 2,641 ms; not a product/merchant result. |
| LLM guardrail ablation | 2 synthetic samples, 0 network calls | Same-fixture local validation only; checked-in simulated structured output, not provider quality. |

These figures describe only the work performed in this repository. In
particular, offline tests and synthetic parser samples are not fetched products.
No Live success is claimed.

## Method

The existing deterministic parser benchmark is
[`backend/benchmarks/run.py`](../backend/benchmarks/run.py). It reads the
checked-in fixture dataset, parses HTML/JSON-LD locally, compares extracted
name, price, SKU, and status with fixture labels, and reports its sample-level
CSV plus JSON summary. It makes zero network calls. The current fixture dataset
contains three synthetic examples, including a price range and a non-product
page. Its labels are test expectations, not manually verified merchant ground
truth.

For a future manually labelled crawler dataset, the network-free evaluator is
[`backend/scripts/crawler_benchmark.py`](../backend/scripts/crawler_benchmark.py).
It calculates per-source metrics with explicit denominators and exports
`report.json` and `records.csv`; it does not fetch URLs or manufacture ground
truth. CSV exports omit URL userinfo, query strings, and fragments to reduce
the chance of exporting tokens or session identifiers. No merchant dataset is
checked in because no source has been approved.

The field-precision denominator is the number of non-null extracted values;
completeness uses non-null ground-truth fields on product-page-verified
observations. Price-evidence coverage is measured over records with an
extracted price. Save success is measured over product-page-verified
observations. Dedup precision is
correctly-merged pairs over all pairs sharing an observed dedup key. Every
zero-denominator ratio is reported as `null`, not zero.

Run it from `backend/`:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m benchmarks.run --output ..\crawler-benchmark-output
.\.venv\Scripts\python.exe -B -X utf8 scripts\crawler_benchmark.py --dataset <annotated-dataset.json> --output ..\crawler-benchmark-output
```

The parser report's `live` result is `N/A`. Do not use parser fixture accuracy,
mock-transport results, or recommendation benchmark values as a crawler Live
metric. Invoke the annotated-dataset evaluator only with an actual,
permission-reviewed dataset.

The separate `benchmarks.llm_spec_ablation` report compares an empty no-LLM
baseline with quote-verified structured output over the same synthetic text.
It records explicit expected/predicted/correct denominators, local validation
latency, zero network calls, and zero estimated cost. It does not call OpenAI or
Gemini and therefore is evidence for schema/quote guardrails only.

## Metrics required before a Live claim

A future manually labelled dataset should retain the source URL, source ID,
fetch timestamp, policy/robots review reference, fetch status, field evidence,
and saved record identifier. It must not store credentials or private approval
documents. Report each ratio with numerator and denominator and break down by
source:

- fetch success and product-page verification rates;
- precision separately for name, price, and SKU against field-level ground
  truth, plus price-evidence coverage and record completeness;
- dedup precision against manually labelled product/variant identities;
- persistence success, and counts of restricted, unknown, and stale results;
- p50/p95 end-to-end latency, including failed attempts;
- HTTPX versus browser versus browser-plus-LLM only when each mode is permitted
  and evaluated on the same URLs and conditions, including LLM cost and latency.

Target 20–50 permitted product URLs only if an approved source and lawful
dataset are available. If fewer are available, state the exact count and avoid
generalizing beyond those records. `LIVE_VERIFIED` requires at least one real
Product and Offer persisted with evidenced price/identity and a reproducible
run; the current result does not meet that threshold.

## Limitations

- No merchant source is enabled in the default registry; live source feasibility
  remains blocked.
- HTTPX connection-time DNS/IP enforcement and browser pinned-proxy enforcement
  are implemented and covered by negative tests. The HTTPX transport integration
  intentionally pins `httpcore>=1.0,<2.0` because it installs a custom network
  backend into the HTTPX connection pool.
- Crawl4AI runtime behavior is verified only on a scraping sandbox, not on a
  merchant. Product ingestion remains unverified until a permitted electronics
  source is available.
- The fixture benchmark does not measure database persistence, source access,
  stale data, deduplication precision, or production latency.
