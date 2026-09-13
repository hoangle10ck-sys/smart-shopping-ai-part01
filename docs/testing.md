# Testing

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
