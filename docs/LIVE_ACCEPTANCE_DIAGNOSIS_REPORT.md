# Live acceptance diagnosis — session 0d288192

Session: `0d288192-8165-4194-a9b6-e3002a764d8a`, created 2026-09-26 05:31:10 UTC.
Read using SQLite `mode=ro` and `PRAGMA query_only=ON`. No Live API calls, user-data writes, migrations or backfill.
Persisted query: `Điện thoại khoảng 10 triệu, camera tốt, pin lâu`.

## A–B. Candidates and rejection

| Candidate | Merchant | Price VND | Availability | Validation | Hard filter |
|---|---|---:|---|---|---|
| Samsung Galaxy S24 Ultra 12GB 512GB | CELLPHONES | 23,990,000 | out_of_stock | VERIFIED_CONTENT, confidence 95 | availability: Sản phẩm hiện không còn hàng. |
| Samsung Galaxy S24 Ultra 12GB 256GB | CELLPHONES | 25,290,000 | out_of_stock | VERIFIED_CONTENT, confidence 95 | availability: Sản phẩm hiện không còn hàng. |

URLs, taken from stored proofs (not fetched again):

- https://cellphones.com.vn/samsung-galaxy-s24-ultra-512gb.html
- https://cellphones.com.vn/samsung-galaxy-s24-ultra.html

Both have phone category from main-page breadcrumbs, confidence 90, no category conflict. Both have same-page identity/price evidence. Neither was rejected for price, identity, category or page validation. Offline replay with availability set to unknown accepts both under the unchanged FLEXIBLE_TARGET rules; this proves the 10-million target did not become a hard ceiling.

## C, F, I. Source conversion and warnings

39 persisted raw rows = 39 unique source URLs = 2 verified direct offers + 37 evidence-only sources. Zero eligible offers and zero recommendations.
Exactly 37 warnings, all unique `Source retained as evidence only: <URL>`, not 36 duplicate warnings.

| Persisted outcome | Count |
|---|---:|
| Non-product/article/category/metadata | 24 |
| Missing price | 2 |
| Missing identity | 1 |
| Fetch failed | 3 |
| Other unverified content | 7 |
| Verified, out of stock | 2 |

24 unique page inspections were requested; 21 fetched content; 3 failed; 2 verified. Fifteen sources were retained without a page request. Nine fetched pages were ultimately classified ARTICLE/NEWS, including `/sforum/`, `/kinh-nghiem-mua-sam/`, specifications, and ambiguous article slugs. Unknown URLs released product slots after classification but still consumed bounded HTTP work. Thus the earlier candidate-cap fix works, while avoidable page work remained.

The two `missing_price` rows are CellphoneS `/mobile/samsung/galaxy-s/s24-series.html` and `/mobile/samsung/galaxy-s.html` catalog pages. `missing_identity` is Amazon `/clp/B0CSDYXF59`. Fetch failures: `chuyensidienthoai.vn/danh-muc/smartphone`, eBay `/b/.../bn_7122009163`, and Tmobile's Inoi A72 product path. Unverified foreign pages include Xiaomi Australia, Samsung US, Amazon and Walmart. One Walmart proof records a redirect to `/blocked`.

No stored HTML is available to establish a sales-page false negative. No acceptance gate was loosened. Canonicalization removed trailing slashes; recorded direct sales URLs retain their full product paths. The evidence does not establish canonicalization as the cause of lost candidates.

## D–E, G. Queries and rounds

These are distinct query owners from persisted rows. Counts below are **stored unique observations**, not raw Tavily result counts. Source persistence is reordered by extraction, so round grouping follows current orchestration, not an archived timing trace.

| Inferred round | Query | Stored rows |
|---|---|---:|
| requirement | điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua giá bán Việt Nam | 5 |
| requirement | điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua chính hãng | 3 |
| model_discovery | "Redmi Note 13 5G" mua | 5 |
| model_discovery | "Samsung Galaxy S24" mua | 5 |
| commercial | điện thoại giá khoảng 10000000 VND giá bán | 3 |
| commercial | điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu mua online | 5 |
| merchant_discovery | điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND camera tốt pin lâu đại lý | 3 |
| merchant_products | site:cellphones.com.vn "Samsung Galaxy S24" giá bán | 4 |
| merchant_products | "Samsung Galaxy S24 Ultra 12GB 512GB" giá | 4 |
| merchant_products | site:chuyensidienthoai.vn điện thoại giá khoảng 10000000 VND giá bán | 2 |

At least 10 provider calls and 7 orchestration rounds are evidenced. Calls returning only duplicate/no rows cannot be recovered from the DB. Provider raw count, per-query duplicate count, complete original model-hint order and exact recorded stop_reason are unavailable. The 24 page attempts equal the default total page budget, consistent with a page-budget stop; this is an inference, not a saved stop event.

The first requirement group yielded 8 persisted evidence sources, zero direct candidates. Model and commercial groups ran and still yielded only evidence. The CellphoneS scoped query supplied the only two direct candidates, both unavailable. Unscoped model queries lacked Vietnam/currency context and their recorded results include foreign stores/catalogs.

## H. Model-hint quality

Offline reconstruction of hints from all final stored observations before this fix included:

Samsung Galaxy S24 Ultra 12GB 512GB; Samsung S24 Ultra 5G; Samsung S25 Ultra;
Redmi Note 13 5g; Redmi Note 13 5G+4G LTE 128GB; Redmi Note 13 5G 128GB ROM;
Samsung Galaxy A26; Samsung Galaxy S24; Samsung S24 Plus; Samsung S24;
Samsung Galaxy A56 5G 8GB 128GB; Oppo A5 5G 4GB/128GB Fullbox;
Samsung Galaxy A37 5G 8GB/128GB Fullbox; Samsung Galaxy A27 5G 6GB/128GB Fullbox;
Redmi Note 15 5G 6GB/128GB Fullbox; Samsung Galaxy S; Samsung Galaxy S26 Plus;
Samsung Galaxy S26 Ultra 5G 12GB; Samsung Galaxy S26 5G 12GB 256GB;
Samsung Galaxy S25 256GB; Samsung Galaxy S25 Plus 256GB; Samsung Galaxy S24 Ultra 5G Cell;
Vivo V30E 12GB 256GB; Sony LYT-600; OPPO A5; Samsung Galaxy A52;
OPPO Reno13 F 5G; Redmi Note 14 Pro 5G; Redmi Note 15 5G; Redmi Note 13 5G Global;
Samsung S24 FE; Samsung Galaxy S24 5G Snap 8; OPPO Reno8 T 5G; OPPO Reno8 Z 5G;
Samsung Galaxy A35 5G; Oppo Find X8s; Oppo Find X8s Plus; Oppo X8s Plus;
Redmi K80 5G; Redmi Turbo 5 Max; Redmi Turbo 4 Pro; Samsung Galaxy S24 FE.

`Sony LYT-600` is a component mention, `Samsung Galaxy S` is a family heading, and suffixes Global/ROM/Fullbox/Cell/Snap are contaminated lookup text. Lookup normalization now removes these suffixes, ignores combined connectivity tokens, filters component/family hints for phone intent, and groups Samsung Galaxy S/A/M/Z/F numeric aliases. Catalog identity, product model fields and scoring remain unchanged. Remaining hints are observations, not verified products or guaranteed in-budget models. Complete post-fix replay hints are in `LIVE_ACCEPTANCE_DIAGNOSIS_REPLAY.json`.

## J. Latency evidence and limits

Persisted search processing time: **50,368.8 ms**. This is the POST search duration; requirement analysis/query generation are in a separate request. Zero recommendations means no per-recommendation LLM explanation work. Images are on the retrieval critical path generally, but both verified offers here were ineligible, so the image loop skips them.

Effective config read from settings, with credentials excluded:

- Retrieval deadline 120 s; maximum 12 queries; page budget 20 product + 4 discovery.
- Provider timeout 10 s per attempt, retry count 0 (no provider retry/backoff configured).
- Shared page client request timeout clamped to 4 s, connect timeout up to 2.5 s, up to four redirect hops; enclosing inspection and retrieval deadlines remain bounded.
- Query concurrency 2, page concurrency 4, per-domain 2, scoped per retrieval.
- Query batches merge deterministically; rounds/batches are awaited sequentially. Low eligible yield permits additional rounds.

**Cannot attribute exact milliseconds to provider vs DNS/connect/read, individual slow domains, extraction/filtering or adaptive rounds:** the old snapshot did not persist performance diagnostics and no matching runtime log was found among repo logs (including ignored files; pytest cache directory is inaccessible). No synthetic timing is substituted for missing historical timing. Verified contributors to avoidable work are the fetched editorial paths and repeated continuation with no progress. Their share of 50 seconds remains unknown.

## K. Changes

1. `retrieval_diagnostics.py`: known `/sforum/`, `/kinh-nghiem-mua-sam/`, specification-only domain retained as metadata; known catalog paths use discovery allocation. Sales-page validation unchanged.
2. `model_hints.py`: cleanup and lookup-only alias dedup described above.
3. `progressive_retrieval.py`: VND exact-model lookup includes `Việt Nam VND`, without budget/requirement prose; stop continuation with `no_progress` after at least three consecutive rounds without new verified identities, after allowing initial stages and two targeted continuation rounds. When stalled, prefer distinct merchants over more unscoped model queries. This preserves the existing TV merchant-diversity regression. Original caps/deadlines/concurrency/pool cleanup remain.
4. Record round durations, per-query provider waits and per-URL inspection durations. These durations overlap and must not be added as independent wall-clock stages. Inspection duration includes fetch and validation; it is not a DNS-only or network-only metric.
5. `search.py`: save retrieval diagnostics as optional metadata alongside result in existing snapshot JSON, in the same transaction. GET reads that metadata; old snapshots return empty diagnostics. Failed refresh preserves the prior successful snapshot and its trace. No schema migration/backfill.
6. `cached_search_service.py`: retrieval scope version 4 prevents previous strategy's cache from masking changed retrieval. Cache TTL and snapshot result semantics unchanged.

## L. Offline fixtures and limitations

`backend/tests/fixtures/live_acceptance_0d288192.json` contains the read-only session observations, proof metadata, snapshot candidates/filter decisions and warnings. It is not a raw provider-response or HTML capture.

Before changes, new regressions failed for editorial allocation, contaminated hints and repeated 36-evidence/two-unavailable-offer work. After changes the repeated-source scenario inspects only two product URLs, never refetches duplicates and stops with `no_progress`; 3/5 valid-offer target tests retain early stop and deadline cancellation cleans pending tasks.

Stored-proof replay returns all 39 observations on every call (deliberate duplicate stress, not the original query sequence): **13 page inspections, 8 provider calls, 2 direct candidates, 0 eligible offers**, `no_progress`. Original persisted session had 24 inspections. These are different workloads; this comparison establishes offline bounded behavior, **not a measured Live latency speedup or improved Live recommendation count**. Reproduce from backend with `.venv/Scripts/python.exe -B -X utf8 scripts/replay_live_acceptance.py`.

## M–R. Final validation

| Check | Result |
|---|---|
| Backend full pytest | 576 collected, 576 passed, 0 failed, 0 errors, 2 warnings; 106.05 s |
| Frontend npm test | 41 passed, 0 failed, 0 skipped |
| npm run lint | PASS, 0 errors / 0 warnings |
| npm run build | PASS |
| npm run test:e2e | 15 passed, 0 failed; 1.4 min; isolated Demo backend |
| git diff --check | PASS; LF/CRLF advisories only |

Backend warnings: Starlette/httpx deprecation and pytest cache write permission. Frontend unit tests emit Node MODULE_TYPELESS_PACKAGE_JSON warnings; E2E emits NO_COLOR/FORCE_COLOR warnings. No unclosed-client/session warnings. Original TV merchant-diversity assertions pass without weakening; snapshot, search failure, scoring, category and budget suites pass.

Live acceptance remains unverified because no additional Live calls were authorized; exact historical timing and full provider results cannot be reconstructed from the available artifacts.

**LIVE ACCEPTANCE DIAGNOSIS FIX = PARTIAL**

Implemented fixes and automated validation pass. The remaining gap is unavailable historical trace and lack of an authorized new Live acceptance, not a hidden test failure. No commit, reset, undo, merge or tag.
