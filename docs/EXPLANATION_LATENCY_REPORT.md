# Final explanation latency optimization

Branch: `feature/live-search-performance`. Existing WIP preserved. No Live API,
production database access/backfill, Git commit, UI redesign or dependency change.

## A. Execution before

`RecommendationService._evaluate` ranked candidates, then iterated them and called
`ExplanationService.explain` synchronously before persisting each recommendation.
Each call could enter the configured Gemini/OpenAI provider loop and its retries.
The explanations only consumed already-computed candidate, requirement, score and
evidence; one product's prose did not depend on another product's explanation.

Archived session `ce69ae93-4497-4f31-8b67-5547543bc859` recorded 23.545s explanation
wall time within 72.718s total. These are historical measurements, not a new Live run.
The old path used the general LLM timeout (30s default) and retry configuration.
It had no single deadline covering primary plus secondary explanation providers.

## B. Execution after

The pipeline prepares all ORM-backed evidence on the caller thread, then submits
only copied Pydantic facts to `ExplanationBatch`. A fixed number of async workers
generate independent explanations. Persistence consumes the returned list in rank
order; scoring and database operations remain on the caller thread.

For the existing synchronous pipeline called from an active event loop, a single
joined helper thread hosts the batch's private async loop. This is not a conversion
of the entire API route to nonblocking I/O. Legacy standalone `explain` remains
compatible; the recommendation pipeline now uses the batch runner.

OpenAI uses an owned `httpx.AsyncClient` context per call. Gemini uses its native
async client context and closes the companion synchronous client in `finally`.
No SDK client is shared across concurrent products. Worker cancellation is drained
before returning. Provider-unavailability state is local to one batch/event loop;
settings and input facts are copied, and performance trace writes stay on the caller.

## C. Concurrency

`EXPLANATION_CONCURRENCY=3` by default, clamped to 1 through 3. The worker count is
also capped by job count. There is no task-per-product unbounded fan-out. This is a
per-batch limit, not a process-wide or cross-request quota controller.

## D. Deadline and failure isolation

`EXPLANATION_TIMEOUT_SECONDS=8` by default. Effective timeout is capped at 8 seconds
and the existing `LLM_TIMEOUT_SECONDS` when lower. Admission starts an item's
deadline; primary and secondary providers share its remaining time. Native client
timeouts receive that remaining budget. SDK retries are disabled for this path.

Each configured provider is attempted at most once per item. A provider exception
may try the configured secondary within the same deadline. Timeout, malformed
output or unsupported claims immediately use deterministic fallback; no LLM repair
call is made. A failed product does not remove recommendations or replace successful
explanations from other products. Tests verify `[gemini, fallback, gemini]` when B
fails, as well as unavailable-provider, cancellation and client-close behavior.

## E. Ordering

Workers write into preallocated positions indexed by input rank. Tests deliberately
finish call 3 before call 1, including persisted results and subsequent GET; output
remains ranks 1, 2, 3. Integration tests coordinate completion with async events
instead of relying on small relative sleep intervals.

## F. Deterministic consistency

The existing approved-statement constraint is applied after schema validation.
Requirement matches, budget score, availability, evidence and Python scores remain
the source of truth. UNKNOWN camera and UNMET battery cannot become positive claims.
Unsupported prose falls back. Tests preserve product facts, score, confidence,
warnings, evidence and saved snapshots. Scoring weights remain 25/30/20/10/5/10.

Batching multiple products into one provider request was not implemented: it would
couple response parsing and failure handling across products. Independent bounded
requests retain per-product validation and fallback.

## G. Offline benchmark

Reproduce from `backend` with
`.\.venv\Scripts\python.exe -B -X utf8 scripts/benchmark_explanation_batch.py`.
The script uses three synthetic inputs and one-second async mock responses; it
never calls a provider. One worker models the old sequential execution.

| Trial | Sequential | Concurrent, limit 3 |
|---|---:|---:|
| 1 | 3.0302s | 1.0154s |
| 2 | 3.0180s | 1.0172s |
| Median | 3.0241s | 1.0163s |

Median reduction: **66.39%**. Peak active calls: 1 before, 3 after. Both retain
output order `[1, 2, 3]`. The separate B-timeout fixture returns
`[gemini, fallback, gemini]` in that same order, with no retry.
Machine-readable results: `EXPLANATION_LATENCY_BENCHMARK.json`.

## H. Retrieval and cache

No retrieval, validator, budget, ranking or query-generation logic was changed in
this phase. A fresh read-only replay of archived rows/proofs still yields 8 provider
calls, 6 rounds, 22 page attempts and 3 eligible offers, preserving the previous
9-to-8 / 7-to-6 / 23-to-22 fix. Stop reason:
`fallback_minimum_no_near_evidence`. This replay uses recorded queries, not new
Live search results or hypothetical unexecuted queries.

Retrieval cache version remains 8. Existing cached explanations already use the
same approved-fact validation semantics; concurrency and deadlines do not require
invalidating valid snapshots. No database schema, response schema or route changes.

## I-O. Fresh validation

| Check | Result |
|---|---|
| Targeted explanation/matching/performance tests | 89 passed, 0 failed, 2 warnings; 6.15s |
| Full backend `python -B -X utf8 -m pytest` | 692 collected, 692 passed, 0 failed, 0 errors, 2 warnings; 59.49s |
| Frontend `npm test` | 41 passed, 0 failed, 0 skipped; 868.5731ms |
| `npm run lint` | PASS, exit 0; 0 errors, 0 warnings |
| `npm run build` | PASS, exit 0; TypeScript and all routes built |
| `npm run test:e2e` | 15 passed, 0 failed; 44.7s; one worker, zero retries |
| `git diff --check` | PASS, exit 0 |
| E2E listeners on 13000/18000 after completion | 0 |

Backend warnings: existing Starlette/httpx TestClient deprecation and Windows
permission denied writing `.pytest_cache/v/cache/nodeids`. Frontend tests emit
MODULE_TYPELESS_PACKAGE_JSON; E2E emits NO_COLOR/FORCE_COLOR warnings. No unclosed
client/session warning was observed. Mock SDK tests explicitly assert both async
and synchronous client cleanup, including timeout and parent cancellation.

Tests use temporary SQLite schemas; E2E uses Demo/local backend with disposable
database and external-provider access disabled. Full regression includes battery
locale parsing, camera aliases, fixed weights, budget modes, OOS/TV retrieval,
failure preservation, cache compatibility and historical snapshots.

Added 17 batch unit cases and 2 pipeline integration cases. Updated existing Live
explanation mocks to native async transports while retaining successful-provider,
timeout, malformed-response and factual-immutability assertions. No tests removed
or weakened. The final full suite includes the event-coordinated ordering tests.

Files changed/created in this phase (11; preceding WIP is separate):

- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/app/services/recommendation/recommendation_service.py`
- `backend/app/services/llm/explanation_batch.py` (new)
- `backend/tests/integration/test_live_explanation.py`
- `backend/tests/integration/test_explanation_batch_pipeline.py` (new)
- `backend/tests/unit/test_explanation_batch.py` (new)
- `backend/tests/fixtures/explanation_jobs.py` (new)
- `backend/scripts/benchmark_explanation_batch.py` (new)
- `docs/EXPLANATION_LATENCY_BENCHMARK.json` (new)
- `docs/EXPLANATION_LATENCY_REPORT.md` (new)

## P. Remaining limitations

- No post-fix Live latency measured. The mock reduction is not a forecast of total
  Live request latency; provider search and page verification time remain unchanged.
- Timeout bounds provider execution, not zero-cost CPU work/client cleanup. More
  than three products queue in waves; five can require two timeout windows.
- Concurrency is per batch. The existing synchronous route bridge still waits for
  the batch; process-wide admission control is outside this phase.
- Strict approved-statement validation can reject otherwise plausible paraphrases.
  Deterministic fallback remains intentional when a provider is slow or ungrounded.
- Historical snapshots are unchanged; no production backfill or new Live acceptance
  claim is made. Existing warnings above remain outside this optimization scope.

FINAL EXPLANATION LATENCY FIX = PASS
