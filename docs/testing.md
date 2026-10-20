# Testing

## Research Catalog checks

Từ `backend/`: `.venv/Scripts/python.exe -m pytest -q tests/test_research_import.py tests/test_research_pipeline.py tests/test_research_safety.py`.
Suite research ban đầu **34 passed**: bounded JSONL/gzip, corrupt/truncated/giant data,
money/identity/idempotency/revisions/conflicts, legacy additive tables, redirect
policy, search/immutable snapshot/comparison/history, VND/USD và unknown specs.
Default pytest không tải metadata và dùng DB tạm; fixtures có nhãn SYNTHETIC TEST.

Thêm `tests/test_research_evaluation.py` kiểm công thức P@K/NDCG, nhãn thiếu,
split và provenance: tổng Research suite **40 passed**. Full backend trước khi
thêm6 tests công cụ độc lập này: **972 passed (91.68s)**.

Frontend: `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`, `npm.cmd run test:e2e`.
E2E mặc định import fixtures trong backend tạm. Muốn xác minh browser với native
metadata thật đã tải hợp lệ, đặt `RESEARCH_E2E_DATA` thành đường dẫn tuyệt đối tới
`backend/data/research` rồi chạy E2E. Vẫn dùng DB tạm, không sửa DB chính.
Lần chạy thực 2026-10-17: **16 passed (42.2s)** với nguồn thật trong Research journey;
15 journeys còn lại là Demo/archived fixtures, không gọi chúng là Live verification.
Sau E2E build lại frontend để bỏ API URL test 18000.

Benchmark nghiên cứu riêng: `python -X utf8 -m scripts.verify_research_catalog`,
`python -X utf8 -m scripts.benchmark_research`. Xem
[rubric/nhãn còn thiếu](RESEARCH_BENCHMARK_RUBRIC.md) và
[báo cáo](RESEARCH_DATA_INTEGRATION_REPORT.md). Không dùng các số này thay Live crawl metrics.

## Backend

From `backend/` on Windows run:

```bash
.\.venv\Scripts\python.exe -B -X utf8 -m pytest
```

On other platforms use `.venv/bin/python -B -m pytest`.
`tests/conftest.py` sets a new temporary SQLite database before application imports,
initializes the schema for every test, and drops it afterward. No manual `init_db()`
or developer `smart_shopping.db` is required. Live-provider tests use mocks.

Phase 6 adds three-state requirement matching, source/field attribution, missing
observations, immutable snapshot metadata, old snapshot compatibility, and cache
copy assertions. Existing Phase 1–5 tests remain in the full suite.

Phase 7 retains that suite and adds two comparison consistency regressions and
three parameterized Demo scenarios. Run separately from `backend/`:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests/integration/test_comparison_api.py -v
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests/integration/test_demo_scenarios.py -v -s
```

Comparison tests verify that later catalog/offer changes cannot change the saved
session's compared price, rating, specifications or score. Legacy sessions without
snapshots use consistent read-only recomputation without backfill. Demo tests cover
headphones, laptop and phone analysis/search, counts, matching, evidence, comparison,
detail, feedback and History. `-s` prints actual scores and match values for demo.md.

## Regression map

| Phase | Main retained coverage |
|---|---|
| 1 | `test_search_api.py`: all-query failure preserves recommendations/warnings/status; `conftest.py`: isolated DB/schema |
| 2 | Category pipeline and analyzer/scoring/hard-filter unit tests: category evidence, requirement values, kg/g, Vietnamese budget parsing |
| 3 | `test_recommendation_snapshot.py`, `test_live_explanation.py`: price/score consistency, counts, mocked modes/timeout/fallback |
| 4 | History/cache integration and cache unit tests: read-only History, hit/miss/expiry/failure conditions |
| 5 | Result metadata integration and frontend result utilities: persisted mode, filter/sort, score display |
| 6 | Matching/evidence backend and frontend render tests; three browser scenarios |
| 7 | Comparison regressions, three Demo scenarios, static Docker/env checks, documentation audit |

Exact final collected/passed/failed/warnings are recorded in [FINAL_AUDIT](FINAL_AUDIT.md).
Passing mocked tests does not verify paid keys, external model availability or
arbitrary Live website extraction.

Collector tests are offline and use `httpx.MockTransport`, static HTML, or a fake
browser renderer. The 2026-10-16 regression completed with 921 backend tests;
the focused collector command completed with 64 tests. Useful focused commands:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests/unit/test_browser_fallback.py tests/unit/test_source_registry_preflight.py tests/unit/test_storefront_api.py
.\.venv\Scripts\python.exe -B -X utf8 -m benchmarks.llm_spec_ablation --output ..\crawler-benchmark-output\llm-spec-ablation.json
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.crawl_products preflight --url "https://APPROVED-HOST/product/example"
```

The final command is a Live network operation only when the URL has an approved
registry entry; an unregistered URL fails before network access. Live ingestion
also requires `--live`, both policy flags, and the registry. See the crawler
runbook for the bounded command and optional browser installation.

## Docker verification

This machine has no Docker CLI/runtime. Dockerfiles, Compose wiring, environment
names, build contexts, secret exclusions, loopback ports, SQLite volume and health
check are reviewed statically. **NOT RUNTIME VERIFIED**: neither `docker compose
build` nor `up` has passed here. Commands for a Docker-equipped machine are in
README; do not replace this limitation with a runtime success claim.

## Frontend

From `frontend/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

`npm test` uses Node's test runner. Component render tests reuse the existing
TypeScript compiler and React server renderer; they do not require a new unit
test framework. `npm.cmd` avoids PowerShell execution policy restrictions on
`npm.ps1`; `npm` works in other shells.

## Browser E2E

Install frontend dependencies with `npm ci`, and install the backend requirements
in `backend/.venv` as described in the README. From `frontend/` run:

```powershell
npm.cmd run test:e2e
```

Playwright Test is the sole new development dependency. It runs headless Microsoft
Edge when installed at the usual Windows path, otherwise Chromium. No browser is
downloaded automatically by this project. On a machine without Edge, install the
Playwright Chromium browser explicitly with `npx playwright install chromium`.
See [Playwright browser channels](https://playwright.dev/docs/browsers) and
[local web servers](https://playwright.dev/docs/test-webserver).

The suite automatically starts:

- FastAPI Demo at `http://127.0.0.1:18000`, using a fresh OS temporary SQLite
  database, empty provider keys, and a guard against external socket connections.
  The launcher verifies the database path before startup; application lifespan
  creates its schema. The test origin is enabled only by this launcher.
- A production Next.js build at `http://127.0.0.1:13000`, compiled with the local
  test backend URL. Browser requests outside these two local origins are blocked.

Both ports must be free: `reuseExistingServer=false` prevents silently using a
developer server/database. Servers are owned and stopped by Playwright. Database
cleanup occurs on normal backend shutdown; force termination on Windows can leave
an isolated `smart-shopping-e2e-*` directory in the OS temp folder. Each invocation
still creates a different database. No application database is touched.

Run without another Next build/dev process in this frontend directory. E2E builds
replace the generated `.next` output, so run `npm run build` afterward before using
`npm start` with your normal backend configuration.

The suite uses one worker and no retries or skipped tests. Scenarios:

1. Enter a request on Home; exercise real Demo analysis/search; navigate to the
   saved results; inspect recommendations, requirement summary, score breakdown,
   explanation and field evidence; filter/sort/reset; open product detail; compare
   two Demo products; submit feedback; open History and reopen the same snapshot.
2. Render all three backend match statuses, values/reasons and structured source
   metadata through a local response fixture. Verify unsafe URLs are not links
   and source text is escaped.
3. Render a pre-Phase-6 snapshot with empty metadata and a failed-search warning
   while keeping its previous recommendations visible (local response fixture).

Failure screenshots/traces are under `frontend/test-results/` (Git-ignored).
The suite never calls Gemini, OpenAI or Tavily.

## Phase 6 response semantics

`RecommendationItem.requirement_matches` contains one item for each explicit
`RequirementData.requirements` entry: `name`, `requested_value`, nullable
`product_value`, `status` (`matched`, `unmet`, `unknown`) and `reason`.
Python reuses the existing requirement scoring comparator and priority values;
only matched entries earn requirement points. Missing or non-comparable data is
unknown, not an observed failure. Budget/category hard filters remain separate.
Qualitative matches (such as ENC for a good microphone) remain deterministic
rubrics, not independently measured product quality.

`EvidenceReport.fields` contains `field`, `value`, nullable `source`, `domain`,
`merchant`, `url`, `retrieved_at`, and source `reliability` (0–100 when known).
Specification paths use `specifications.<name>`. Attribution requires a matching
product/offer association and the same normalized value in that session's raw
observation. Untraceable fields are omitted; the cheapest offer is not assumed
to be the source of every product field. Timestamps describe the stored observation,
not the current shop price. No new reliability or confidence values are invented.

Both arrays are stored in the existing version-1 JSON recommendation snapshot.
GET and cache copying preserve them; old snapshots default to empty arrays without
database writes or backfill. No SQL schema, route, cache-key, TTL, or score-weight
changes are part of Phase 6.
# Collector/benchmark upgrade checks

All default tests remain offline. Collector tests use `httpx.MockTransport` for JSON-LD,
missing price, SKU ranges, 403/429/CAPTCHA, timeout, redirect SSRF and body limits. Direct
URL integration monkeypatches the collector and proves the path does not require Tavily.

Run the reproducible fixture benchmark from `backend/`:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m benchmarks.run --output ..\docs\benchmark-results
```

```bash
.venv/bin/python -B -m benchmarks.run --output ../docs/benchmark-results
```

The committed report identifies its synthetic dataset and denominators. Live smoke is N/A
and must remain opt-in after policy/permission review.

No repository database file existed during the final audit, so migration-on-a-copy was
N/A. `test_additive_migration.py` instead creates a disposable legacy SQLite database,
copies the legacy row semantics through the additive migration twice, and verifies that
the original price and product link remain readable. Demo integration and E2E tests clear
all API keys and use isolated temporary databases.

Playwright E2E uses `e2e/global-setup.mjs` to own the isolated Python and Next processes;
the teardown explicitly terminates their process trees on Windows. The full suite completed
with 15 passed and a clean exit.
