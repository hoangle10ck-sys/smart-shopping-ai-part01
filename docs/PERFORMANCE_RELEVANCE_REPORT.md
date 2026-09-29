# Performance / relevance audit — session 981f372a

Offline audit of saved evidence. No Live API; production SQLite was opened read-only only when exporting the fixture.

## A–B. Timing and latency

| Metric | Previous ms | Latest ms | Delta ms |
|---|---:|---:|---:|
| requirement_analysis_ms | 0.000 | 0.000 | +0.000 |
| clarification_ms | 0.000 | 0.000 | +0.000 |
| query_generation_ms | 0.000 | 0.000 | +0.000 |
| search_provider_ms | 20376.868 | 31359.357 | +10982.489 |
| product_discovery_ms | 1087.280 | 2990.788 | +1903.508 |
| product_verification_ms | 7567.347 | 10961.880 | +3394.533 |
| page_fetch_ms | 10816.035 | 15343.427 | +4527.392 |
| verification_ms | 2554.750 | 2398.545 | -156.205 |
| extraction_ms | 245.846 | 443.251 | +197.405 |
| filtering_ms | 0.092 | 0.287 | +0.195 |
| scoring_ms | 0.008 | 0.420 | +0.412 |
| explanation_ms | 0.000 | 4156.228 | +4156.228 |
| total_search_ms | 31805.650 | 54266.444 | +22460.794 |

Analysis/clarification/query-generation zeros mean not measured in this search request. Their separate request times are not recoverable from this snapshot.
Provider timing is accumulated batch wall time. Page-fetch and verification timing can overlap/nest with rounds; these metrics must not be summed as disjoint stages.
Total recorded round wall time: 44877.479 ms. Image resolution has no separate persisted timer; the residual cannot be attributed precisely.
Measured increases: 9→12 provider calls, 6→9 rounds, 15→24 page attempts. Provider wait +10.982s, verification batch wall +3.395s, discovery CPU +1.904s; explanation adds 4.156s. The provider/network component dominates. No evidence establishes a provider quota error.

### Every retrieval round

| Round | Wall ms | New direct / merchant / model / child | Cumulative pages / eligible | Continue/stop |
|---|---:|---|---|---|
| 1 requirement | 4383.885 | 1 / 0 / 15 / 0 | 3 / 0 | not satisfied; novelty reset no_progress |
| 2 model_discovery | 7054.193 | 8 / 3 / 1 / 0 | 11 / 0 | not satisfied; novelty reset no_progress |
| 3 commercial | 3946.058 | 0 / 0 / 13 / 0 | 12 / 0 | not satisfied; novelty reset no_progress |
| 4 merchant_discovery | 4905.347 | 0 / 0 / 0 / 0 | 12 / 0 | not satisfied; one stale round below bounded no_progress limit |
| 5 merchant_products | 5867.108 | 1 / 1 / 0 / 0 | 13 / 0 | not satisfied; novelty reset no_progress |
| 6 merchant_products | 4022.14 | 0 / 0 / 7 / 0 | 13 / 0 | not satisfied; novelty reset no_progress |
| 7 alternative_model | 5907.231 | 4 / 0 / 0 / 0 | 18 / 2 | not satisfied; novelty reset no_progress |
| 8 alternative_model | 5752.325 | 4 / 1 / 1 / 0 | 23 / 2 | not satisfied; novelty reset no_progress |
| 9 alternative_model | 3039.192 | 1 / 0 / 0 / 0 | 24 / 2 | page_budget reached |

Round 1 queries:
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua giá bán Việt Nam` — 3538.266 ms, 5 rows; error=None.
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua chính hãng` — 2286.893 ms, 5 rows; error=None.

Round 2 queries:
- `"Vivo V30E 12GB 256GB" mua Việt Nam VND` — 3415.675 ms, 5 rows; error=None.
- `"OPPO A5" mua Việt Nam VND` — 4440.778 ms, 5 rows; error=None.

Round 3 queries:
- `điện thoại giá khoảng 10000000 VND giá bán` — 2987.45 ms, 5 rows; error=None.
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua online` — 2613.814 ms, 5 rows; error=None.

Round 4 queries:
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu đại lý` — 4701.355 ms, 5 rows; error=None.

Round 5 queries:
- `site:cellphones.com.vn "vivo V30e 5G 12GB/256GB" giá bán Việt Nam VND` — 3566.324 ms, 2 rows; error=None.

Round 6 queries:
- `site:thegioididong.com điện thoại giá khoảng 10000000 VND giá bán` — 3746.827 ms, 5 rows; error=None.

Round 7 queries:
- `"Samsung Galaxy A52" giá Việt Nam VND` — 2342.944 ms, 5 rows; error=None.

Round 8 queries:
- `"OPPO Reno 10" giá Việt Nam VND` — 3171.903 ms, 5 rows; error=None.

Round 9 queries:
- `"OPPO Reno10 5G 8GB/256GB" giá Việt Nam VND` — 2424.834 ms, 5 rows; error=None.

### Domain budgets / cancellation

| Domain | Active ms | Attempts | Consecutive failures | Skipped |
|---|---:|---:|---:|---:|
| anhducdigital.vn | 980.244 | 1 | 0 | 0 |
| bachlongstore.vn | 545.096 | 1 | 0 | 0 |
| cellphones.com.vn | 6004.004 | 4 | 1 | 0 |
| chuyenphanphoi.vn | 1164.287 | 2 | 0 | 0 |
| clickbuy.com.vn | 308.691 | 1 | 0 | 0 |
| coin98.net | 728.762 | 1 | 0 | 0 |
| didongmy.com | 309.744 | 1 | 0 | 0 |
| dienmaycholon.com | 969.089 | 1 | 0 | 0 |
| dienthoaivui.com.vn | 369.743 | 1 | 0 | 0 |
| duchuymobile.com | 729.855 | 2 | 0 | 0 |
| ericsson.com | 165.502 | 1 | 1 | 0 |
| mtcgame.com | 201.91 | 2 | 2 | 1 |
| news.samsung.com | 1008.934 | 1 | 0 | 0 |
| nguyenkim.com | 421.602 | 1 | 0 | 0 |
| oppo.com | 1933.398 | 2 | 0 | 0 |
| thegioididong.com | 1714.504 | 2 | 0 | 0 |

Domain active time is union wall time, not a sum of parallel fetches. CellphoneS exhausted the 6000ms domain budget (6004ms including cancellation overhead). Two MTCGAME failures suppressed its third URL. The stored proof for CellphoneS Reno10 records timeout. Other HTTP/network failures are listed in the JSON; no historical unclosed-client event can be inferred from this snapshot.

## C–D. Source expansion and relevance

Provider rows 45→57; unique sources 33→48. URL overlap=11, added=37, absent from latest=22. This is not simply the same 33 plus 15.
Classification: {'direct_product': 4, 'article_review_news_video': 27, 'listing': 3, 'likely_product_unverified': 8, 'irrelevant_noise': 6}; child products=0.
Four currency/game-credit rows came from the full quoted OPPO A5 query. Wikipedia/Ericsson came from the full quoted OPPO Reno10 query. No saved query was standalone 5G or VND. The provider drifted; the scheduler lacked an explicit irrelevant-intent gate.
Old-phone articles were evidence-only but seeded old/cheap models and new-model progress. Their content was not certified product evidence. Repeated broad discovery and Reno 10/Reno10 alias splitting used bounded query/page capacity.

## E. Why only two weak offers

Stop reason was page_budget (24), not target satisfaction. Four verified offers include two out-of-stock and two eligible A52 seller offers. Both eligible offers have empty specifications and camera/battery UNKNOWN; both lie below the preferred 9.4–10.6m window. They remain valid flexible-budget fallback offers.
A52 Like New: 2,499,000 VND, budget=0, requirement=0, final=36. A52 Anh Duc: 8,190,000 VND, budget=24.58, requirement=0, final=31.15. Fixed weights are unchanged.
Observed but unsearched: Xiaomi 15T Pro, Redmi Note 14 Pro, OPPO Reno13 F, Redmi Note 15 and other models (complete states in JSON). Their actual in-range, in-stock offers are NOT established by article mentions. Exact Xiaomi 15T is a regression fixture, not a certified latest-session offer.
Model order was source/discovery order, not a preference for easier direct pages. It nevertheless selected older A52 ahead of later relevant mentions. Live success for those alternatives cannot be inferred without provider results.

## F–G. Changes

- Explicit currency/game-credit and generic-network intents: retain diagnostic metadata, zero page fetch, no model/merchant/direct progress. No URL/domain blacklist. Unknown product identity remains discoverable.
- Use the article title’s explicit budget topic to prioritize observed model hints. This does not assign a price to a model or change offer evidence.
- Treat Reno 10/Reno10 capacity/connectivity spellings as the same lookup budget only; catalog/offer identities remain unchanged.
- Prefer unseen alternatives when existing offers are weak; avoid generic commercial/dealer rounds while useful unsearched models exist.
- Keep eligible and strong-fit counts separate. Target 3/5 still stops early; two strong models stop after a stale round when no unseen model remains. Two weak offers do not cause a quality stop.
- Standalone 5G/VND cannot form model queries; Xiaomi 15T remains valid. Cache retrieval version 7 prevents reuse of old orchestration results.

## H. Fixed-input fixture before / after

Fixed batch of all 48 archived sources, frozen page proofs. Only relevance gate toggled. Not Live latency or a replay of unrecorded queries.
Page attempts: 23→19; verified: 4→4; eligible: 2→2.
This isolates scheduling; it is NOT a new Live benchmark or evidence of a particular post-fix response time.

## I–N. Validation

Fresh validation in this turn:

| Check | Result |
|---|---|
| Final focused relevance/performance run | 35 passed, 0 failed, 1 pytest-cache warning; 6.51s |
| Full backend `python -B -X utf8 -m pytest` | 638 collected, 638 passed, 0 failed, 0 errors, 2 warnings; 111.59s |
| Frontend `npm test` | 41 passed, 0 failed; 2.291s |
| `npm run lint` | Exit 0; 0 errors, 0 warnings |
| `npm run build` | Exit 0; compile, TypeScript, static generation pass |
| `npm run test:e2e` | 15 passed, 0 failed; 1.4m; one worker, no retry |
| Git branch | `feature/live-search-performance` |
| `git diff --check` | Exit 0; no whitespace errors |

Backend warnings: Starlette/httpx test-client deprecation and Windows permission denied writing `.pytest_cache/v/cache/nodeids`. Frontend test runner reports the existing MODULE_TYPELESS_PACKAGE_JSON warning. E2E reports NO_COLOR/FORCE_COLOR warnings. No unclosed client/session warning appeared.

Tests use a disposable SQLite database prepared by `tests/conftest.py`; E2E uses Demo/local servers and its own temporary database, with external sockets blocked. No Live provider was called. E2E left zero listeners on 13000/18000.

Full regression passed: strict direct-page validation, alternate merchant/out-of-stock recovery, direct-product priority, TV broad fallback, HARD_MAX/FLEXIBLE_TARGET/RANGE, fixed 25/30/20/10/5/10 scoring, target=1 cache separation, old-version cache rejection (including newly covered v6), historical snapshots, previous-session preservation on provider failure.

Resource checks retain the shared HTTP session context manager and closure on cancellation, query/page/per-domain semaphores, domain failure/time budgets and deterministic query-order merge. No timeout/deadline/concurrency cap was increased.

Files changed in this diagnosis (earlier WIP remains):

- `backend/app/services/search/progressive_retrieval.py`
- `backend/app/services/search/model_hints.py`
- `backend/app/services/search/cached_search_service.py`
- `backend/app/services/search/retrieval_relevance.py` (new)
- `backend/tests/integration/test_candidate_discovery_api.py`
- `backend/tests/unit/test_live_search_performance.py`
- `backend/tests/unit/test_performance_relevance.py` (new; 15 tests)
- `backend/tests/fixtures/live_relevance_981f372a.json` (new)
- `backend/scripts/audit_performance_relevance.py` (new)
- `docs/PERFORMANCE_RELEVANCE_AUDIT.json` (new)
- `docs/PERFORMANCE_RELEVANCE_REPORT.md` (new)

The existing exhaustion test now asserts the authorized strong-fit/no-progress stop at four queries, preserving its offer-count and page-count assertions. A new cache case rejects retrieval v6. No tests were deleted. No database schema, API routes, UI, scoring weights, budget policy or validator relaxation was introduced in this diagnosis. Build regenerated `next-env.d.ts` to the existing tracked production declaration; no manual restore was performed. No Git commit.

## O. Remaining limitations

- Live latency/recall after the fix is unmeasured, as requested. No claimed 54s→X Live improvement.
- Archived HTML and responses for unexecuted queries are absent. No omitted URL can be declared a valid missed offer from these records alone.
- Condition is only present in names such as Like New/trôi bảo hành; there is no structured condition field or price normalization by condition. No new used/refurbished exclusion policy.
- Article budget-topic relevance is a lookup hint, not proof of current price, stock, camera or battery. Provider freshness and supported model parsing remain limited.
- Numeric timings overlap; separate historical analysis/image durations cannot be reconstructed exactly.

Offline implementation and regression validation passed. Overall Live performance/relevance acceptance remains PARTIAL: no post-fix Live run was authorized, so a substantial latency reduction and stronger real offers have not been demonstrated. No further Live calls or Git commit were made.

## Full 48-source audit

| # | Classification | Requested | URL |
|---|---|---|---|
| 1 | direct_product | True | https://cellphones.com.vn/dien-thoai-vivo-v30e.html |
| 2 | direct_product | True | https://www.anhducdigital.vn/samsung-galaxy-a52-128gb-black-chinh-hang-p1254.html |
| 3 | direct_product | True | https://cellphones.com.vn/samsung-galaxy-a52.html |
| 4 | direct_product | True | https://www.duchuymobile.com/samsung-galaxy-a52-tbh |
| 5 | article_review_news_video | False | https://hungmobile.vn/tin-tuc/top-dien-thoai-duoi-10-trieu-dang-mua-nhat.html |
| 6 | listing | True | https://clickbuy.com.vn/dien-thoai-7-8-trieu.html |
| 7 | article_review_news_video | False | https://cellphones.com.vn/sforum/dien-thoai-tam-trung-dang-mua-nhat |
| 8 | article_review_news_video | True | https://dienthoaivui.com.vn/dien-thoai-gia-re-cho-hoc-sinh |
| 9 | article_review_news_video | False | https://mobappy.co.jp/top-dien-thoai-android-gia-re-dang-mua-nhat-2026-goi-y-dang-tien-cho-moi-nhu-cau |
| 10 | article_review_news_video | False | https://dienmaycholon.com/kinh-nghiem-mua-sam/top-dien-thoai-duoi-10-trieu-chup-anh-dep-dang-mua-hien-nay |
| 11 | article_review_news_video | False | https://www.youtube.com/watch?v=sbPRprYOxdg |
| 12 | article_review_news_video | False | https://www.youtube.com/watch?v=etGY7JVoUDw |
| 13 | likely_product_unverified | True | https://www.nguyenkim.com/nen-mua-dien-thoai-nao-NKUQ2075.b |
| 14 | article_review_news_video | True | https://www.didongmy.com/vivo-v30e-gia-bao-nhieu-lieu-co-dang-mua- |
| 15 | likely_product_unverified | True | https://dienmaycholon.com/dien-thoai-di-dong/vivo-v30e-12gb256gb |
| 16 | likely_product_unverified | True | https://chuyenphanphoi.vn/san-pham/dien-thoai-vivo-v30e-5g-12gb-256gb-trang-8193.html |
| 17 | likely_product_unverified | True | https://chuyenphanphoi.vn/san-pham/dien-thoai-vivo-v30e-5g-12gb-256gb-nau-do-8194.html |
| 18 | likely_product_unverified | True | https://www.thegioididong.com/dtdd/vivo-v30e-12gb |
| 19 | article_review_news_video | False | https://fptshop.com.vn/tin-tuc/danh-gia/oppo-a5-pro-5g-191394 |
| 20 | irrelevant_noise | True | https://www.mtcgame.com/vi/razer-gold/razer-gold-vietnam/razer-gold-vietnam-vnd-30000 |
| 21 | irrelevant_noise | True | https://www.mtcgame.com/vi/razer-gold/razer-gold-vietnam/razer-gold-vietnam-vnd-20000 |
| 22 | irrelevant_noise | False | https://www.mtcgame.com/vi/razer-gold/razer-gold-vietnam/razer-gold-vietnam-vnd-100000 |
| 23 | irrelevant_noise | True | https://coin98.net/mua-btc-bang-vnd |
| 24 | article_review_news_video | False | https://24hstore.vn/review-san-pham/dien-thoai-duoi-10-trieu-n8676 |
| 25 | listing | False | https://www.chotot.com/tags/mua-ban-dien-thoai/dien-thoai-duoi-1-trieu |
| 26 | listing | True | https://cellphones.com.vn/bo-loc/dien-thoai-gia-re-duoi-2-trieu |
| 27 | article_review_news_video | False | https://phuongtung.vn/bai-viet/nhung-chiec-dien-thoai-thong-minh-co-gia-cao-nhat-viet-nam |
| 28 | article_review_news_video | False | https://hungmobile.vn/tin-tuc/dien-thoai-duoi-3-trieu.html |
| 29 | article_review_news_video | False | https://bloganchoi.com/tag/dien-thoai-pin-trau-cau-hinh-manh/feed |
| 30 | article_review_news_video | False | https://bloganchoi.com/tag/dien-thoai-samsung-galaxy-m62/feed |
| 31 | article_review_news_video | False | https://bloganchoi.com/tag/dien-thoai-vivo-y33s/feed |
| 32 | article_review_news_video | False | https://bloganchoi.com/tag/dien-thoai-realme-c25/feed |
| 33 | article_review_news_video | False | https://bloganchoi.com/tag/dien-thoai-realme-9i/feed |
| 34 | article_review_news_video | False | https://cellphones.com.vn/sforum/dien-thoai-vivo-pin-trau |
| 35 | article_review_news_video | False | https://www.thegioididong.com/tin-tuc/top-5-dien-thoai-gia-10-trieu-dang-mua-1561196 |
| 36 | article_review_news_video | False | https://www.thegioididong.com/hoi-dap/top-10-dien-thoai-tam-5-trieu-dang-mua-nhat-hien-nay-1436835 |
| 37 | article_review_news_video | False | https://www.thegioididong.com/game-app/top-10-dien-thoai-cu-duoi-1-trieu-choi-game-tot-nhat-2022-1486633 |
| 38 | article_review_news_video | False | https://www.thegioididong.com/hoi-dap/top-10-smartphone-thiet-ke-dep-gia-re-dang-mua-tai-the-1436705 |
| 39 | article_review_news_video | False | https://www.thegioididong.com/hoi-dap/top-8-dien-thoai-android-10-gia-re-dang-mua-tai-the-gioi-1417545 |
| 40 | article_review_news_video | True | https://news.samsung.com/vn/ra-mat-galaxy-a52-a52-5g-va-a72 |
| 41 | article_review_news_video | True | https://bachlongstore.vn/samsung-galaxy-a52-8gb-128gb-cu.html |
| 42 | article_review_news_video | True | https://www.oppo.com/vn/newsroom/press/reno10-chinh-thuc-mo-ban |
| 43 | likely_product_unverified | True | https://www.duchuymobile.com/oppo-reno10-5g |
| 44 | likely_product_unverified | True | https://www.thegioididong.com/dtdd/oppo-reno10 |
| 45 | likely_product_unverified | True | https://cellphones.com.vn/oppo-reno10.html |
| 46 | article_review_news_video | True | https://www.oppo.com/vn/newsroom/press/ra-mat-reno10-series-5g |
| 47 | irrelevant_noise | False | https://en.wikipedia.org/wiki/5G |
| 48 | irrelevant_noise | True | https://www.ericsson.com/en/5g |
