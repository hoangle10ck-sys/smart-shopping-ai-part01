# Crawler track progress

Updated: 2026-10-16 (Asia/Ho_Chi_Minh)

## Worktree and baseline

- The worktree contained pre-existing modifications before this track. They
  were preserved; no reset, commit, or push was performed.
- Initial backend baseline: **860 passed, 1 failed, 1 warning** (861 collected).
  The failure was
  `tests/unit/test_oos_recovery.py::test_recovery_deadline_cancels_probe_and_never_retries`;
  the recovery probe's deadline timeout could fire slightly before the
  `time.monotonic()` deadline, leaving a few milliseconds reported as usable.
  This was fixed by latching a global deadline as exhausted when the enclosing
  `asyncio.timeout` reports that it expired.
- Baseline frontend: `npm.cmd test` **44 passed**; lint and build exited 0.
- Latest focused Retry-After and benchmark-export tests: **17 passed**. The full suite
  also includes the collector, API, persistence, migration and benchmark tests.
  The benchmark and Retry-After behavior were validated without network access.
- Final full backend run after fixing the deadline: **909 passed, 1 warning**
  (909 collected). The warning is Starlette's existing deprecation warning
  about `httpx` with `starlette.testclient`.
- Final frontend run: `npm.cmd test` **44 passed**; `npm.cmd run lint` and
  `npm.cmd run build` exited 0; `npm.cmd run test:e2e` **15 passed**.
- The most recent focused Retry-After/benchmark command from `backend/`:

  ```powershell
  .\.venv\Scripts\python.exe -B -X utf8 -m pytest tests\unit\test_crawler_benchmark.py tests\unit\test_source_registry_preflight.py
  ```

  The focused run had no warnings.
- The benchmark fixture has three synthetic HTML/JSON-LD samples; it is not a
  real-source dataset. No real merchant product URL has been fetched.
- Source feasibility and rationale: [source matrix](CRAWLER_SOURCE_MATRIX.md)
  and [ADR](CRAWLER_ADR.md).

## Task status

| Task | Status | Evidence / remaining work |
|---|---|---|
| T00 | DONE | Backend/frontend baseline, call path, source matrix and ADR documented. Live source selection remains blocked. |
| T01 | DONE | Typed registration, observation, evidence, failure and status contracts; empty registry and Live defaults fail closed. Offline contract tests pass. |
| T02 | DONE | HTTPX resolves and validates at `connect_tcp`, then pins the socket to the checked IP while retaining the hostname for Host/TLS SNI/certificate validation. SSRF, rebinding, IPv4/IPv6, redirect, proxy and reconnect tests pass. |
| T03 | DONE | WooCommerce Store API adapter has bounded paging, field-level JSON paths, currency minor-unit handling, variable-product safeguards and offline tests. No approved merchant exists for Live testing. |
| T04 | DONE | Registered HTTPX product-page flow with JSON-LD parsing, direct URL integration, same-source evidence and partial results is covered by offline tests. No Live source is approved. |
| T05 | DONE | Crawl4AI 0.9.5 and Chromium are installed and exercised. Browser traffic is constrained by a pinned CONNECT proxy and route guard; sandbox, timeout, DOM, process and RSS bounds are enabled. The permitted JS sandbox smoke returned HTTP 200 and verified rendered DOM. |
| T06 | DONE | OpenAI/Gemini specs fallback verifies exact quotes, rejects offer fields, bounds input/output/time, caches verified results, and has a same-fixture offline guardrail ablation. No paid-provider quality claim is made. |
| T07 | DONE | Product/variant/offer/price-observation persistence, idempotency, rollback and additive migration tests exist. `CrawlRun.robots_checked_at` is an additive nullable column. |
| T08 | DONE | Registered sources and direct product URLs feed normalization and recommendation; API evidence is not mislabeled as product-page validation. Direct collector integration tests pass. |
| T09 | IN_PROGRESS | Parser, annotated-dataset, and LLM guardrail benchmarks plus a bounded `crawl_products` preflight/Live CLI are offline-tested. Real URLs, Live metrics, and browser Live ablation remain N/A because no source is approved. |
| T10 | DONE | Runbook, evaluation, architecture/database/testing/README references updated. Full backend passes; frontend tests/lint/build and browser E2E pass. Blocked Live tasks remain explicitly non-DONE. |

### 2026-10-16 catalog batch checkpoint

- Added `CatalogIngestionService` and `python -m scripts.ingest_catalog` for a
  bounded, idempotent preload of phones, laptops/desktops, and headphones into
  the existing catalog/recommendation database.
- The command fails closed when no approved enabled source is configured. No
  Live merchant was approved or fetched at this checkpoint, so the Live status
  remains `LIVE_NOT_VERIFIED / BLOCKED` and the real-record count remains 0.
- Offline targeted verification: `22 passed` for catalog ingestion,
  normalization, direct collector integration, variant persistence, and the
  WooCommerce Store API. A full run initially found one floating-point deadline
  clamp failure in explanation batching (`909 passed, 1 failed`); the timeout
  is now explicitly capped at its configured budget and re-verified. The final
  full run reached `909 passed, 1 failed`; the remaining failure is the existing
  20 ms timing-sensitive OOS recovery test, which did not start its fake probe
  before the deadline under the loaded Windows runner. Collector-focused tests
  and compilation pass; the same OOS test passes alone (`1 passed`). This does
  not indicate a catalog-ingestion regression.

### 2026-10-16 browser, LLM, and operator CLI checkpoint

- Added an optional Crawl4AI 0.9.5 adapter and `requirements-browser.txt`.
  Browser fallback is considered only for an approved HTTP response identified
  as an empty JavaScript app shell. It uses no stealth/proxy/click/scroll/form
  behavior and returns rendered DOM to the deterministic JSON-LD parser.
- Added bounded renderer results, final-host/DOM-size/CAPTCHA checks, actionable
  `BROWSER_UNAVAILABLE`, and fake-renderer coverage. Focused browser/product-page
  run: `22 passed`.
- LLM spec fallback now caches quote-verified results, rejects price/SKU/stock/
  seller/rating/warranty/shipping/voucher fields even when nested as a spec, and
  has a two-sample same-fixture offline ablation (`6 passed`, zero network calls).
- Added `python -m scripts.crawl_products preflight|ingest`; ingestion requires
  `--live`, both policy flags, an approved registry entry, and caps of at most 5
  products / 2 pages. Focused CLI/browser/LLM run: `17 passed`.
- No merchant was added or contacted. Live counters remain zero.
- Final regression after this checkpoint: backend `921 passed, 1 warning`;
  frontend unit `44 passed`; frontend lint and production build exited 0;
  Playwright E2E `15 passed`. Collector-focused regression was `64 passed,
  1 warning`. The warning is Starlette's existing `httpx` TestClient
  deprecation notice.
- Fail-closed CLI check against an unregistered placeholder returned
  `SOURCE_NOT_PERMITTED` before any network request.
- Additive `init_db()` initialized the local SQLite schema successfully. Direct
  inspection returned Product 0, Variant 0, Offer 0, PriceObservation 0 and
  CrawlRun 0; these zeros are reported rather than filling the catalog with
  mock records.

## Live evidence

- Approved electronics merchants: **0**
- Live product URLs fetched: **0**
- Verified products persisted from Live: **0**
- Verified offers persisted from Live: **0**
- Current Live status: **LIVE_NOT_VERIFIED / BLOCKED**

No API documentation example, sitemap, search result, fixture or mock response
is Live evidence. See [the runbook](CRAWLER_RUNBOOK.md) for the registry and
safe operating procedure and [the evaluation](CRAWLER_EVALUATION.md) for
metrics and limitations.

## Remaining blockers

1. Establish a merchant-specific permission basis and approve one source before
   any Live request.
2. Run bounded Live product ingestion, repeat it for idempotency, and prove the
   recommendation path reads persisted real records.
3. Complete the real-URL benchmark and paired LLM/no-LLM comparison; do not substitute
   fixture results for Live metrics.

### 2026-10-16 crawler unblock checkpoint

- T02 is resolved. `PinnedAsyncNetworkBackend` performs authoritative DNS
  validation at connection time and connects to the selected public IP literal;
  httpcore retains the original origin for Host, TLS SNI and certificate checks.
- Focused collector regression: **65 passed**; the security/preflight subset is
  **31 passed**.
  Coverage includes DNS rebinding, IPv4/IPv6, IPv4-mapped IPv6, loopback,
  private/link-local/metadata/reserved/multicast addresses, redirects, proxy
  environment isolation, reconnect/retry, Host and TLS SNI.
- Crawl4AI 0.9.5, Playwright 1.64 and Chromium 156 were installed. Live runtime
  smoke against the explicitly provided scraping sandbox
  `https://quotes.toscrape.com/js/` returned `LIVE_SMOKE_OK`, HTTP 200, rendered
  DOM 8,985 bytes, 10 observed requests, one off-host font blocked, and 2,641 ms
  end-to-end elapsed time at `2026-10-16T14:26:21.849447+00:00`.
- Registry records now support `allowed_paths`; live defaults remain fail-closed.
  WooCommerce's official documentation confirms a public customer-facing Store
  API, but this does not grant merchant-specific bulk collection permission.
  Best Buy requires an API key and its developer terms restrict third-party
  pricing/product analysis, so it was not enabled.
- Product Live status remains **BLOCKED_SOURCE_PERMISSION / LIVE_NOT_VERIFIED**.
  Preflight for an unregistered URL returned `SOURCE_NOT_PERMITTED`; bounded
  ingest returned `SOURCE_NOT_PERMITTED` because both live policy flags remain
  false. SQLite remains Product 0, Variant 0, Offer 0, PriceObservation 0.
- Final backend regression after this checkpoint: **938 passed** in 84.34 s.
