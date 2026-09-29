# Requirement match / latency — ce69ae93

Read-only persisted-session audit; no Live requests. Original snapshot and production database remain untouched.

## A. Exact persisted timing

| Metric | Latest ms | Delta vs 54.266s session |
|---|---:|---:|
| requirement_analysis_ms | 0.000 | +0.000 |
| clarification_ms | 0.000 | +0.000 |
| query_generation_ms | 0.000 | +0.000 |
| search_provider_ms | 25811.482 | -5547.875 |
| product_discovery_ms | 4645.522 | +1654.734 |
| product_verification_ms | 12141.592 | +1179.712 |
| page_fetch_ms | 14842.177 | -501.250 |
| verification_ms | 5024.281 | +2625.736 |
| extraction_ms | 458.460 | +15.209 |
| filtering_ms | 0.367 | +0.080 |
| scoring_ms | 3.980 | +3.560 |
| explanation_ms | 23544.545 | +19388.317 |
| total_search_ms | 72718.625 | +18452.181 |

Total increased 18.452181s; explanation increased 19.388317s, while provider search decreased 5.547875s. Three explanations are generated sequentially by RecommendationService. Stored modes: Gemini, Gemini, fallback. The snapshot has no per-product/provider-attempt timings or error details; it cannot establish which call timed out or exhausted quota.
Analysis/clarification/query-generation zeros are unmeasured in this separate search request, not zero-cost operations. Fetch is aggregate overlapping work; verification/discovery timers nest inside round wall times and must not be summed as separate stages.
Sum of retrieval-round wall durations: 41681.068ms. Explanation total: 23544.545ms. Image resolution/postprocessing have no dedicated historical timing; residual time cannot be assigned precisely.

## B. Rounds and counts

9 provider calls, 7 rounds, 23 page attempts, 20 product attempts. Stop reason: candidate_budget; cap=20. 43 discovered URLs, 41 persisted observations, 4 candidates, 3 eligible offers. The two remaining pending sources have no persisted page proof.

| Round | Wall ms | New direct/model/merchant/eligible | Cumulative pages/eligible |
|---|---:|---|---|
| 1 requirement | 6030.585 | 2/17/0/0 | 3/0 |
| 2 model_discovery | 6704.236 | 5/2/2/2 | 8/2 |
| 3 merchant_products | 4908.116 | 3/3/2/0 | 12/2 |
| 4 merchant_products | 6927.574 | 1/0/0/0 | 15/2 |
| 5 alternative_model | 4081.718 | 3/1/1/0 | 19/2 |
| 6 alternative_model | 6668.8 | 3/2/0/1 | 22/3 |
| 7 alternative_model | 6360.039 | 1/1/0/0 | 23/3 |

Round 1:
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua giá bán Việt Nam` — provider 4753.33ms; 5 rows; error=None.
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua chính hãng` — provider 3031.948ms; 5 rows; error=None.

Round 2:
- `"POCO X8 Pro" mua Việt Nam VND` — provider 2603.494ms; 5 rows; error=None.
- `"OPPO Reno14 F" mua Việt Nam VND` — provider 2952.221ms; 5 rows; error=None.

Round 3:
- `"Redmi K80 5G" giá Việt Nam VND` — provider 2804.751ms; 5 rows; error=None.

Round 4:
- `site:thegioididong.com "Redmi K80 12GB 256GB" giá bán Việt Nam VND` — provider 4656.937ms; 5 rows; error=None.

Round 5:
- `"Oppo Find X8s Plus" giá Việt Nam VND` — provider 2214.895ms; 5 rows; error=None.

Round 6:
- `"Oppo Find X8s" giá Việt Nam VND` — provider 2886.45ms; 5 rows; error=None.

Round 7:
- `"Redmi Turbo 5 Max" giá Việt Nam VND` — provider 5095.521ms; 5 rows; error=None.

Largest round: #4, 6927.574ms, no new eligible offer; provider wait 4656.937ms. Round #6 (6668.800ms) produced the third eligible offer and must be preserved. Round #7 cost 6360.039ms, added zero eligible offers, and exhausted the candidate cap. Its last provider call alone took 5095.521ms.

## C–D. Deterministic root causes

- Battery parsed a generic decimal string: 8.500 became 8.5. The mAh-specific parser now recognizes dot/comma thousands grouping, retaining true decimals and rejecting malformed groups. The phone threshold is still 4000mAh; hours, weight and RAM parsers are unchanged.
- Exact spec-key matching omitted camera sau/trước and rear/front camera. Generic camera now reads these aliases. OIS remains the pre-existing qualitative rubric; megapixels alone remain UNKNOWN. An explicitly requested front camera cannot borrow rear-camera OIS.

| Product | Old camera / battery | Corrected camera / battery | Old final | Corrected final |
|---|---|---|---:|---:|
| OPPO Find X8 16GB 512GB | unknown / matched | matched / matched | 55.8 | 70.8 |
| OPPO Reno14 5G 12GB 256GB | unknown / matched | matched / matched | 55.0 | 70.0 |
| POCO X8 Pro Max 12GB 256GB | unknown / unmet | matched / matched | 39.8 | 69.8 |

Corrected scores are offline recomputations of the archived candidates, not a rewrite of historical recommendations. The score weights remain 25/30/20/10/5/10.

## E. Explanation consistency

Previously the payload omitted structured requirement_matches and returned arbitrary LLM text without a semantic gate. Gemini therefore asserted camera suitability while the matcher reported UNKNOWN.
The payload now includes deterministic matches plus approved statements about matches, budget, availability and evidence. LLMs may select/order those statements. Every response field is checked against its approved values; unsupported narrative returns deterministic fallback immediately, without a repair call. Required caveats are restored if omitted. This intentionally limits paraphrasing to guarantee consistency; it does not claim that keyword detection can validate arbitrary prose.
Flexible budget wording now says preferred range/fallback rather than falsely treating the target as a hard maximum. Missing stock stays unknown. No LLM can alter price, specifications or scores.

## F. Budget/retrieval and fixed-sequence replay

All three observed prices (13.99m, 15.5m, 19.49m) remain eligible FLEXIBLE_TARGET fallbacks. Earlier code promoted structured discovery hints with missing prices as if they fit the budget. Now known near-range evidence ranks before unknown and far-range hints; verified price is attached only to the same observed model. Near-range unseen alternatives are prioritized before far fallback recovery.
Stop after at least three unique eligible offers with zero budget-fit scores when no unsearched model has explicit near-range price evidence. One/two weak offers still allow bounded discovery; explicit near-range alternatives still continue. Deadlines, page/domain bounds, OOS filtering and strict page validation stay unchanged.
Recorded query sequence, archived rows/proofs only; stop checked between rounds. Not a replay of changed model-query order or Live timing.
Replay: provider queries 9→8; rounds 7→6; page attempts 23→22; retained eligible URLs=3; stop=fallback_minimum_no_near_evidence.
The skipped historical round cost 6.360s then; this is not a measurement or prediction of post-fix Live latency. Changed query ordering is not reconstructed for unexecuted queries.

## G–M. Validation

Fresh validation for this diagnosis:

| Check | Result |
|---|---|
| Targeted matching/explanation/retrieval suite | 170 passed, 0 failed, 2 warnings; 32.06s |
| Focused recheck after fixing two full-suite regressions | 83 passed, 0 failed, 1 warning; 2.05s |
| Full backend `python -B -X utf8 -m pytest` | 673 collected, 673 passed, 0 failed, 0 errors, 2 warnings; 53.63s |
| Frontend `npm test` | 41 passed, 0 failed; 966.981ms |
| `npm run lint` | PASS, exit 0; 0 errors / 0 warnings |
| `npm run build` | PASS, exit 0; TypeScript and all routes built |
| `npm run test:e2e` | 15 passed, 0 failed; 51.0s, one worker, no retries |
| `git diff --check` | PASS, exit 0; new text files also checked for trailing whitespace |
| Branch | `feature/live-search-performance` |

Backend warnings: existing Starlette/httpx deprecation and Windows permission denied writing `.pytest_cache/v/cache/nodeids`. Frontend tests emit MODULE_TYPELESS_PACKAGE_JSON; E2E emits NO_COLOR/FORCE_COLOR warnings. No unclosed-client warning was observed. E2E left zero listeners on ports 13000/18000.

Backend tests prepare a clean temporary SQLite schema; E2E uses Demo/local backend and its own disposable database. No test uses the real `smart_shopping.db` or paid Live providers. Full regression includes OOS/alternate merchant, motorcycle official suggested-price semantics, TV fallback, strict direct verification, budget modes, weights, session failure preservation and snapshot compatibility.

Added 34 requirement/latency tests and a cache-v7 rejection case. Existing successful-provider mocks now return approved statements while retaining malicious numeric extra fields, timeout/invalid-response tests and score/evidence immutability assertions. No tests were deleted or weakened.

Files changed/created in this diagnosis (earlier WIP preserved):

- `backend/app/services/scoring/scoring_engine.py`
- `backend/app/services/llm/explanation_service.py`
- `backend/app/services/search/progressive_retrieval.py`
- `backend/app/services/search/cached_search_service.py`
- `backend/tests/unit/test_explanation_service.py`
- `backend/tests/integration/test_live_explanation.py`
- `backend/tests/integration/test_candidate_discovery_api.py`
- `backend/tests/unit/test_requirement_latency.py` (new)
- `backend/tests/fixtures/live_match_ce69ae93.json` (new)
- `backend/scripts/audit_requirement_latency.py` (new)
- `docs/REQUIREMENT_LATENCY_AUDIT.json` (new)
- `docs/REQUIREMENT_LATENCY_REPORT.md` (new)

The complete working tree has 62 changed/untracked files, including preceding phases. No frontend component/UI edit was made. The build regenerated the standard `next-env.d.ts` declaration; it is no longer different from the tracked production declaration.

## N. Limitations

- No post-fix Live latency/recall measured. The main latency cost, sequential provider explanation calls, is not proven faster by this offline run.
- Exact LLM paraphrases outside approved statements fall back, even when plausibly correct. This trades phrasing variety for verifiable consistency.
- Price-topic article hints do not establish a near-budget offer. After the fallback minimum, unknown-price models may remain unsearched; this is a bounded recall/latency tradeoff, not a hard filter.
- OIS and 4000mAh are existing heuristics, not new measurements of camera quality or battery runtime.
- Historical snapshots preserve their recorded matches/scores/explanations. No backfill of the real database.
- Cache retrieval version 8 avoids reusing earlier retrieval behavior; cache tests include v7 rejection. No schema/routes/UI/dependency changes.

No Live API, reset/undo/restore/clean, commit, merge or tag.

Offline matching/explanation fixes and all regressions PASS. Overall latency acceptance remains PARTIAL because the dominant sequential LLM call cost and post-fix Live latency are unverified; no unmeasured speedup is claimed.

FINAL REQUIREMENT MATCH LATENCY FIX = PARTIAL
