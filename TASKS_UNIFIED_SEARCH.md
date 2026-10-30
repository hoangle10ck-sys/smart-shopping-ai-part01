# TASKS — Unified Automatic Multi-Source Search

**Mục tiêu:** một luồng nghiệp vụ duy nhất để người dùng mô tả nhu cầu; hệ thống tự đọc dữ liệu nội bộ, tìm tất cả nguồn ngoài khả dụng/được phép trong giới hạn vận hành, lưu quan sát có provenance, rồi lọc, chấm điểm và đề xuất. Người dùng không chọn Demo/Research/Live hay phải bật từng sàn để bắt đầu tìm kiếm.

**Phạm vi:** backend, frontend, persistence, source policy, tests và tài liệu. Đây là task plan; các mục đều `TODO` cho đến khi có bằng chứng kiểm thử. Giữ nguyên `TASKS.md` cho Collector Track, không ghi đè lịch sử hoặc các thay đổi khác trong working tree.

## 0. Nguyên tắc nghiệp vụ và an toàn

- Hệ thống tự dò **mọi nguồn đã tích hợp, bật, có quyền truy cập và được khai báo trong source registry**; “mọi nguồn” không có nghĩa là Internet vô hạn hoặc vượt cơ chế kiểm soát truy cập.
- Đọc catalog hiện có trước; tra catalog nghiên cứu và nguồn trực tuyến khả dụng trong cùng một search run. Không chỉ gọi nguồn ngoài khi số sản phẩm nội bộ dưới một ngưỡng nếu người dùng yêu cầu tìm kiếm đa nguồn đầy đủ.
- Có thể chạy các nguồn độc lập song song, nhưng phải giới hạn concurrency, timeout, tổng thời gian, số query/page/URL, rate theo domain và kích thước response. Khi hết budget, dừng có kiểm soát và báo nguồn/phạm vi chưa hoàn tất.
- Không bịa sản phẩm, offer, giá, tồn kho, rating, review, thông số, URL, nguồn hoặc trạng thái xác minh. Không tạo dữ liệu giả để đủ Top-K.
- Demo fixture chỉ dùng trong Demo/QA và phải gắn nhãn `MOCK_DEMO`; tuyệt đối không trộn vào kết quả mua hàng thật như một offer. Có thể cung cấp chế độ demo riêng ngoài luồng production nếu cần.
- Dữ liệu nghiên cứu/lịch sử (ví dụ Amazon Reviews 2023) phải giữ nhãn và thời gian tham chiếu; không trình bày như giá/offer hiện hành hoặc dùng để khẳng định còn hàng.
- Chỉ lưu dữ liệu thu thập hợp lệ/được phép. Mỗi observation cần gắn nguồn, URL, thời gian quan sát, phương pháp thu thập, trạng thái freshness/verification và evidence theo field khi có. Giữ raw payload theo giới hạn và chính sách retention.
- Nếu source bị chặn, không được phép, timeout hoặc thiếu API key, đánh dấu rõ trạng thái (ví dụ `ACCESS_RESTRICTED`, `SOURCE_NOT_PERMITTED`, `FETCH_ERROR`, `NOT_CONFIGURED`); không lặng lẽ báo “đã tìm mọi nơi”.
- Kết quả không đầy đủ vẫn có thể trả về nếu hữu ích, nhưng phải có warnings, coverage/source outcomes và nói rõ phần chưa kiểm tra. Không coi search thành công một nguồn là toàn bộ nguồn đều đã được tìm.
- Giữ snapshot phiên bất biến: giá/điểm/evidence trong kết quả cũ không bị cập nhật ngầm theo catalog mới.

## 1. Audit hiện trạng — chưa phải nghiệm thu

- [x] Đã xác định Home hiện có dropdown “Chế độ dữ liệu”, checkbox Shopee/Lazada và input URL trực tiếp: `frontend/app/page.tsx`.
- [x] Đã xác định `SearchRequest.search_scope` mặc định là `platforms`; route chỉ gọi `UnifiedSearchService` khi scope là `auto`.
- [x] Đã xác định `UnifiedSearchService` hiện đọc database + research, nhưng external supplement chỉ chạy khi catalog nội bộ “thin”; Demo loại fixtures; Live phụ thuộc config/key; Collector hiện fail-closed.
- [ ] Chạy lại audit trên working tree trước khi triển khai; ghi rõ thay đổi trước đó, test baseline và blocker nguồn thật. Không giả định trạng thái code đã đồng bộ với tài liệu.

## 2. P0 — Chốt contract và semantics nguồn

### U1.1 Search request mặc định là automatic
- [ ] Chuyển contract request/UI để `POST /api/search` luôn chạy luồng automatic unified theo mặc định; loại bỏ phụ thuộc `search_scope=auto` do frontend phải tự chọn.
- [ ] Quyết định compatibility: request cũ có `search_scope=platforms` được xử lý như alias có thời hạn hoặc trả validation có hướng dẫn; không âm thầm chạy một semantics khác.
- [ ] Bảo đảm API search/retry/refresh/history đều giữ cùng semantics automatic; không để nút refresh quay về pipeline legacy.

### U1.2 Source registry và trạng thái khả dụng
- [ ] Chuẩn hóa interface/source registry chung cho database catalog, research catalog, Tavily discovery, storefront API, direct URL và các collector được duyệt.
- [ ] Mỗi source trả outcome chuẩn: `configured`, `available`, `attempted`, `succeeded`, số candidates/observations, thời lượng, warnings, lỗi có phân loại, trạng thái policy và phạm vi đã kiểm tra.
- [ ] Chỉ gọi nguồn ngoài khi cấu hình hợp lệ và policy cho phép; nguồn không khả dụng vẫn được biểu diễn rõ trong response, không bị bỏ khỏi coverage report.
- [ ] Xác định quy tắc dữ liệu Research và Demo tại contract: research có thể tham khảo nhưng phải tách semantics; Demo không được xem là dữ liệu mua hàng thật.

### U1.3 Search coverage và chiến lược tiếp tục tìm
- [ ] Thực hiện search trên từng source khả dụng trong registry trong một request; không bỏ qua Live chỉ vì catalog đạt `unified_min_fresh_products`.
- [ ] Dùng progressive retrieval: query/category/model/merchant phù hợp; tiếp tục khi còn budget và có tiến triển hoặc còn nguồn khả dụng chưa thử.
- [ ] Dừng theo budget có cấu hình (deadline, query/page/URL/concurrency/per-domain/bytes), ghi nguyên nhân dừng và sources chưa hoàn tất.
- [ ] Tránh gọi trùng cùng query/URL/source trong một run; có dedup xuyên nguồn theo identity/model/variant mà không gộp nhầm biến thể.
- [ ] Không tuyên bố “tìm thấy tất cả sản phẩm trên Internet”; response/UI mô tả chính xác các nguồn và thời điểm đã kiểm tra.

## 3. P0 — Thu thập, xác minh và lưu dữ liệu

### U2.1 Ingestion có provenance
- [ ] Nối các kết quả từ nguồn ngoài qua pipeline hiện có: validate → extract → normalize → identity/variant resolution → dedup → persistence.
- [ ] Chỉ đưa candidate có bằng chứng về sản phẩm thật vào catalog; discovery result/URL chưa xác minh không được coi như offer đã xác thực.
- [ ] Upsert Product/Variant/Offer theo identity ổn định; lưu PriceObservation bất biến cho từng lần quan sát theo schema hiện có.
- [ ] Bảo đảm observation chứa source, URL, observed_at, phương pháp, currency, giá và evidence phù hợp; field không có chứng cứ để `unknown/null`.
- [ ] Giao dịch/rollback phải tránh lưu trạng thái nửa chừng; lỗi ở một source không làm mất dữ liệu hợp lệ từ source khác hoặc snapshot thành công trước đó.
- [ ] Thêm retention/size bounds cho raw payload và dữ liệu lỗi theo chính sách; không xóa snapshot lịch sử cần thiết.

### U2.2 Ranking hợp nhất đúng semantics
- [ ] Hợp nhất các candidates sau ingestion và chạy hard filter/scoring/ranking một lần trên tập dữ liệu hợp lệ.
- [ ] Không cộng điểm hoặc so sánh giá giữa currency/đơn vị không tương thích; historical reference không được coi là current offer.
- [ ] Tách Product Suitability khỏi Offer Quality; chỉ đánh giá offer bằng giá, freshness, availability, merchant/source evidence hiện có.
- [ ] Top-K là tối đa; nếu không đủ sản phẩm phù hợp thì trả ít hơn và giải thích lý do.
- [ ] Snapshot lưu candidates, filter decisions, ranking, source outcomes, evidence, timestamp và semantics của từng data type.

### U2.3 Bảo vệ nguồn ngoài
- [ ] Duy trì SSRF/DNS/IP validation, scheme/host allowlist, robots/policy/permission checks, redirect validation và content-type/size limits.
- [ ] Không bypass login, CAPTCHA, anti-bot, rate limit hoặc điều khoản website; dừng/fallback khi bị hạn chế.
- [ ] Đặt timeout/retry/backoff có giới hạn; rate limit theo host; không retry lỗi policy hoặc lỗi vĩnh viễn.
- [ ] Không ghi API key, cookie, query nhạy cảm hoặc raw response không cần thiết vào logs.
- [ ] Cấu hình Live source fail-closed khi chưa khai báo quyền/registry/API key cần thiết.

## 4. P1 — Frontend: một luồng tìm kiếm tự động

### U3.1 Home search form
- [ ] Bỏ dropdown **“Chế độ dữ liệu”** và nhánh riêng gọi `researchSearch()` trong submit flow thông thường.
- [ ] Bỏ checkbox chọn Shopee/Lazada nếu sản phẩm chốt tự động tìm mọi source khả dụng; source selection thuộc cấu hình hệ thống, không phải lựa chọn bắt buộc của người dùng.
- [ ] Giữ mô tả nhu cầu và URL sản phẩm trực tiếp tùy chọn; URL trực tiếp là một đầu vào bổ sung, không thay thế discovery đa nguồn.
- [ ] Thay controls bị bỏ bằng mô tả dễ hiểu, ví dụ: “Tự tìm trong dữ liệu đã lưu và các nguồn trực tuyến khả dụng; hệ thống chỉ hiển thị dữ liệu có nguồn.” Không hứa hẹn mọi website.
- [ ] Thông báo rõ rằng một số nguồn có thể không truy cập được hoặc dữ liệu có thể cũ; không trình bày checkbox/logo như bằng chứng nguồn đang hoạt động.

### U3.2 Progress, results và provenance
- [ ] Hiển thị các giai đoạn có thật: phân tích nhu cầu → kiểm tra catalog → tra nguồn khả dụng → xác minh/lưu → xếp hạng. Không tạo phần trăm hoặc tiến độ giả.
- [ ] Trong kết quả, hiển thị source coverage/outcomes: đã kiểm tra, thành công, bị hạn chế, chưa cấu hình, lỗi và thời gian quan sát.
- [ ] Phân biệt rõ `CURRENT_OFFER`, dữ liệu catalog cũ/stale, `HISTORICAL_RESEARCH` và `MOCK_DEMO`; không gọi chung tất cả là “giá hiện tại”.
- [ ] Hiển thị evidence/source cho giá, availability và thông số quan trọng; dùng unknown khi không có chứng cứ.
- [ ] Thiết kế loading, partial success, zero results, all sources unavailable, timeout, error/retry và warnings bằng tiếng Việt, không dead-end.
- [ ] Giữ filter/sort/compare/feedback/history tương thích với unified snapshot; không để UI tự sửa score hoặc provenance.

### U3.3 Accessibility và responsive
- [ ] Giữ label/ID cần thiết cho test và accessibility sau khi đổi form; kiểm tra keyboard, focus, screen reader names.
- [ ] Kiểm tra viewport mobile/desktop, không overflow; controls chạm được và warnings/source list đọc được trên mobile.

## 5. P1 — Tests, observability và docs

### U4.1 Backend tests (offline, không gọi nguồn trả phí)
- [ ] Test request mặc định vào unified flow; compatibility cho request cũ.
- [ ] Test database đầy/thiếu vẫn tra tất cả source ngoài được cấu hình và được phép.
- [ ] Test nhiều nguồn thành công, một nguồn lỗi, tất cả nguồn lỗi, timeout/budget exhaustion, policy restricted và source unconfigured.
- [ ] Test ingestion chỉ lưu dữ liệu có evidence; idempotency/dedup; không gộp variant; historical/demo không thành current offer.
- [ ] Test currency, freshness, unknown fields, hard filter, ranking, Top-K tối đa và snapshot consistency.
- [ ] Test không tạo dữ liệu giả khi nguồn trả rỗng/lỗi; lỗi một nguồn không rollback thành công của nguồn khác.
- [ ] Dùng fake providers, local fixtures và temporary DB; không dùng real key, Internet hoặc website thật trong CI.

### U4.2 Frontend tests/E2E
- [ ] Test không còn mode dropdown/branch Research bắt buộc/checkbox source bắt buộc.
- [ ] Test một câu query gửi request automatic; URL trực tiếp có hoặc không đều hoạt động.
- [ ] Test loading, partial results/source warnings, historical labels, empty result và retry.
- [ ] Cập nhật Playwright scenarios theo flow mới; bảo đảm local network guard không gọi Internet.

### U4.3 Tài liệu và telemetry
- [ ] Cập nhật `docs/architecture.md`, `docs/api.md`, `docs/database.md`, `docs/demo.md`, README và OpenAPI semantics.
- [ ] Mô tả rõ source registry/cách thêm nguồn, policy gate, budget, freshness, persistence, retention và status vocabulary.
- [ ] Thêm request/correlation ID và per-source/per-stage duration/counters; log lỗi có cấu trúc nhưng redact secrets/PII.
- [ ] Báo cáo riêng `OFFLINE_TESTED`, `LIVE_VERIFIED`, `LIVE_PARTIAL`, `LIVE_RESTRICTED`, `LIVE_NOT_VERIFIED`; không suy từ mock test sang Live.

## 6. Thứ tự triển khai và phụ thuộc

| Phase | Phạm vi | Phụ thuộc | Trạng thái |
|---|---|---|---|
| U0 | Re-audit working tree, baseline và API contract | — | TODO |
| U1 | Backend mặc định unified + source registry/coverage + progressive search | U0 | TODO |
| U2 | Persistence/provenance, ranking hợp nhất, policy & security tests | U1 | TODO |
| U3 | Home UI bỏ mode/source selection; progress/results/partial-state | U1 contract ổn định | TODO |
| U4 | Backend/frontend regression, E2E, docs, telemetry | U1–U3 | TODO |
| U5 | Opt-in Live verification trên source được phép; migration/operations nếu cần | U4 + source approval | BLOCKED cho đến khi có nguồn được duyệt và môi trường phù hợp |

## 7. Definition of Done

- [ ] Người dùng tìm bằng một luồng duy nhất, không chọn Demo/Research/Live hoặc từng sàn.
- [ ] Search run đọc catalog nội bộ và thử mọi source đã cấu hình/khả dụng/được phép trong budget; coverage và nguồn chưa thử được trả rõ.
- [ ] Dữ liệu hợp lệ được chuẩn hóa, dedup và lưu kèm provenance/freshness; lần tìm lại không nhân bản record.
- [ ] Demo fixture, historical research và current offers được tách semantics; không dữ liệu nào bị trình bày sai loại.
- [ ] Mọi recommendation có evidence phù hợp; thiếu dữ liệu được đánh dấu unknown; không bịa hoặc ép đủ Top-K.
- [ ] Search partial/failure/zero-results có response hữu ích, warning chính xác và snapshot nhất quán.
- [x] Offline backend suite, frontend unit/lint/build và Playwright pass; test không gọi Internet/API trả phí.
- [ ] Live chỉ được ghi `LIVE_VERIFIED` khi có kiểm tra thật trên nguồn được phép, có ngày giờ, số lượt fetch, số observation lưu và bằng chứng; nếu không thì ghi blocker chính xác.

## 8. Checkpoint log

### Re-audit checkpoint — October 22, 2026

This checkpoint supersedes stale assumptions in the initial audit above; the
older checklist remains as implementation history/backlog, not as a claim that
every item is still untouched.

- [x] Automatic unified route is present; `search_scope` defaults to `auto` and
  legacy `platforms` is treated as a deprecated alias by the route.
- [x] Frontend home/results and API types have already been changed toward one
  automatic flow; inspect current UX/tests before further UI edits.
- [x] Tavily and explicitly configured SearXNG adapters are present with
  concurrent fan-out and URL deduplication.
- [x] Legacy API docs no longer claim `source_platforms` selects Shopee/Lazada.
- [x] Cache key distinguishes configured provider setup; live source is no
  longer mislabeled as Tavily-only.
- [ ] Remove/retire stale collector integration tests and remaining API/docs
  references; retain only explicit historical notes where useful. October 29
  audit found the direct-URL collector tests still cover supported URL ingestion;
  their two unused `source_platforms` request fields were removed and the
  targeted tests passed. Legacy specification/report examples remain clearly
  historical and are preserved as project evidence.
- [ ] Run backend targeted and full tests, frontend test/lint/build, and
  `git diff --check`; record actual command output and resolve failures.
- [ ] Build and run Docker only where Docker Engine is available.
- [ ] Configure at least one authorized live provider and perform opt-in live
  acceptance with timestamp, provider outcome, evidence and persisted counts.
- [ ] Review SearXNG AGPL-3.0 implications before distributing or offering a
  hosted service using a SearXNG deployment.

**Status at this October 22 checkpoint:** code inspection only; automated checks
and live provider behavior had not yet been confirmed. The October 29
verification checkpoint below supersedes this status for local checks. No
provider configuration is assumed, and provider coverage is limited to
integrations explicitly configured and permitted by the operator.

```text
[U0/U1/U2/U3/U4/U5] STATUS: TODO | IN_PROGRESS | DONE | BLOCKED
Files changed:
Exact tests/commands and results:
Sources attempted / availability:
Observations/products/offers persisted:
Live status and evidence:
Known limitations/blockers:
Next task:
```

### Verification checkpoint - October 29, 2026

- [x] Backend full suite after source status/message updates: `backend\.venv\Scripts\python.exe -m pytest -x --tb=short` - 1025 passed.
- [x] Frontend tests: `npm test` - 49 passed; `npm run lint` and `tsc --noEmit` passed.
- [x] Production build: `npm run build` passed on Next.js 16.4.1 after the source-status UI change.
- [x] Playwright: `npm run test:e2e` - 20 passed using an isolated temporary SQLite database and loopback-only network guard; after adding assertions for the unconfigured-source message and history timestamp/year, `npm run test:e2e -- e2e/shopping.spec.ts` - 4 passed.
- [x] Docker Compose config/build passed. Isolated Compose runtime passed: PostgreSQL and backend healthy, `/api/system/status` returned `ok`, and frontend returned HTTP 200. Its project-specific volume and containers were removed afterward.
- [x] Removed the backend's unused mount of the PostgreSQL data volume at `/data`; the backend connects to PostgreSQL through `DATABASE_URL`.
- [x] Fixed accidental literal `\n` suffixes in the unified search orchestrator and its test. The stack startup exposed this syntax error; `py_compile`, targeted tests (29 passed), and the full backend suite passed afterward.
- [x] `git diff --check` passed. Existing staged `.next/trace*` deletions and other pre-existing workspace edits were preserved.
- [x] Regression fixes include timestamps for verified search metadata, generic computer category detection, and UI clarification for unknown product categories.
- [x] Audited current README, API, architecture, and Demo fixture guidance against the automatic Home/API path. Corrected stale instructions that described fixture search as a Home Demo mode; clarified that missing provider/catalog evidence can yield zero recommendations.
- [x] Reconciled the current `/api/search` route/orchestrator with README and architecture: the unified path reads the verified catalog and historical catalog, checks configured web providers on each run, and does not use the legacy cross-session cache. Updated the flow diagram and cache/runtime guidance.
- [x] Corrected the crawler runbook so `DEMO_MODE` is not described as collector permission. Updated the historical demo page: current tests assert empty unified search returns zero, while old fixture tables are explicitly non-current examples.
- [x] Unified source status now distinguishes an unconfigured provider, a failed configured query, and an unavailable/restricted source; unit coverage added for those labels.
- [x] The results banner now says only `Tìm kiếm hợp nhất`; exact source availability appears in the source panel. Targeted browser E2E confirms the missing-provider state is visible.
- [x] History browser flow confirms the displayed `datetime` matches the API's UTC `created_at` and includes the localized year; history persistence/detail behavior remains covered by API and E2E tests.
- [x] `SearchRequest.direct_urls` now trims whitespace, removes blank entries and deduplicates before enforcing the five-unique-URL limit. A regression test reproduced the prior 422 for six entries containing only one unique URL; focused unit/API tests passed and the post-fix backend suite passed (1027 tests). API docs now describe the input normalization. The `platforms` compatibility alias also has route-level test coverage and is documented precisely.
- [x] Follow-up collector/research operator-doc audit corrected the stale DNS rebinding limitation in `docs/CRAWLER_RUNBOOK.md`; the referenced pinned-transport unit suite ran: `backend/.venv/Scripts/python.exe -B -X utf8 -m pytest tests/unit/test_collector_network_policy.py -q` - 16 passed. `git diff --check` completed with exit code 0.
- [x] Fixed direct product URLs being silently skipped when neither Tavily nor SearXNG was configured. A new API integration regression first failed with `fetched == []`; after the orchestrator change, `tests/integration/test_direct_collector_api.py` plus `tests/integration/test_search_api.py` passed (13), and the full isolated backend suite passed (1028). Frontend checks after the fix: 64 unit tests, lint, `tsc --noEmit`, production build, and Playwright E2E (20) passed. No external search key or merchant request was used.
- [x] Reconciled `docs/testing.md` with current evidence: E2E uses a disposable database with synthetic catalog offers (not Demo mock offers), and recorded Compose local runtime verification is distinct from production readiness.
- [x] E2E runner explicitly clears inherited SearXNG configuration and disables collector flags/registry in addition to paid provider keys; post-hardening Playwright completed 20/20 with exit code 0.
- [x] E2E global setup refuses occupied 13000/18000 ports and checks spawned-process liveness before readiness. Full Playwright passed (20); a controlled occupied-18000 run confirmed setup exits before starting tests and explicitly refuses reuse. `docs/testing.md` now describes the implemented isolation.
- [x] `npm audit --audit-level=high` found a high-severity advisory for transitive `zod@4.4.3`; updated only the existing lockfile entry to `4.6.7`. Re-audit reports 0 vulnerabilities; frontend tests (49), lint, type-check, build, and full Playwright (20) pass afterward.
- [ ] `pip-audit` remains `NOT_RUN` because the tool is not installed. A manual
  OSV batch query checked 145 packages in `backend/.venv`: upgraded existing
  packages Brotli 1.2.0→1.2.1, certifi 2026.7.22→2026.10.23, filelock
  4.2.0→4.2.4, and NLTK 3.10.3→3.10.4 in that local venv; `pip check` found no
  broken requirements and the post-update backend suite passed (1025 tests).
  A follow-up OSV query still flags optional Pillow 12.3.0 (advisories require
  Pillow 13.0.0) and the venv's pip 23.2.1. No repository dependency files
  changed. Pillow's major upgrade and pip tooling upgrade remain pending the
  repository's dependency approval gate. OSV records:
  https://osv.dev/vulnerability/GHSA-22hg-r758-rrw9
  https://osv.dev/vulnerability/GHSA-4xh5-x5gv-qwph
- [x] Reviewed the SearXNG license surface: upstream declares AGPL-3.0; this repository configures an external endpoint and does not bundle SearXNG code/image. A specific hosted or modified deployment still needs its own legal review.
- [ ] Live provider acceptance remains `LIVE_NOT_VERIFIED`: no paid/provider request was made under the no-live-call constraint. Provider configuration was inspected using presence booleans only; no values were exposed. SearXNG is unset; collector flags are off and its registry is empty. No Live product/offer evidence was created.
- [ ] Public deployment security was `NOT_VERIFIED` at this checkpoint: history was shared within the local database and the MVP had no user isolation or API rate limits. The history-isolation gap is addressed by the October 29, 2026 privacy checkpoint below; rate limits and the broader public-deployment review remain outstanding. Compose binds to loopback; do not expose it publicly until the remaining controls are addressed.
- [x] Finished the current operator-document and historical collector/research
  reference audit. Current README/API/architecture/demo/runbook/source matrix
  align with fail-closed source policy, no fixture-to-offer behavior, and
  `LIVE_NOT_VERIFIED` status. Historical Demo wording in original SPEC/report
  artifacts is subordinate to `PROJECT OVERRIDES` or dated. Corrected one stale
  runbook limitation: collector HTTP transport now pins each TCP connection to
  a validated public IP; its unit test is in
  `backend/tests/unit/test_collector_network_policy.py`. Optional browser
  rendering still needs network-isolated egress controls.

```text
Verification status: OFFLINE_TESTED
Live status: LIVE_NOT_VERIFIED
```

### Local SearXNG discovery checkpoint - October 29, 2026

- [x] Checked Docker and runtime configuration without printing secrets:
  Docker Engine 29.4.3 / Compose 5.1.3 was available (8 CPUs, about 7.6 GiB
  memory). No SearXNG container or configured backend endpoint existed before
  this check. `backend/.env` has `SEARXNG_BASE_URL` unset, collector flags are
  false, policy confirmation is false, and the source registry is empty.
- [x] Added an opt-in Compose `searxng` profile using upstream image tag
  `ghcr.io/searxng/searxng:2026.10.23-629368e40`. Its port binds only to
  `127.0.0.1:8080`; the small `searxng/settings.yml` override inherits upstream
  defaults and enables `html` plus `json`. Default Compose startup still does
  not start SearXNG or configure the backend endpoint. The cache volume is
  named and persistent.
- [x] Compose validation passed with the profile disabled and enabled:
  `docker compose --env-file .env.example config --quiet` and
  `docker compose --env-file .env.example --profile searxng config --quiet`
  (both exit code 0). The pinned image was pulled and the local container
  started; `/` returned HTTP 200. Runtime use was about 120 MiB.
- [x] Live adapter smoke query `máy tính xách tay Việt Nam` against
  `http://127.0.0.1:8080` returned 5 JSON results through `SearXNGProvider`
  (exit code 0). Results included category/brand pages at thegioididong.com,
  cellphones.com.vn, fptshop.com.vn, and hp.com. This validates discovery and
  URL parsing only; results did not establish current SKU prices, stock,
  ratings, or merchant offers. SearXNG logs showed `ahmia` and `torch` engines
  failed to register; other engines returned results.
- [x] Added offline coverage for successful parse, empty results, timeout,
  HTTP 503, malformed payloads, and unsafe URLs. Targeted test command
  `python -B -X utf8 -m pytest tests/unit/test_searxng_provider.py
  tests/unit/test_multi_search_provider.py -q` - 9 passed, exit code 0.
- [ ] The application endpoint remains unconfigured by default. To use the
  Compose service, set `SEARXNG_BASE_URL=http://searxng:8080` when starting the
  backend. Live product/offer verification remains `LIVE_NOT_VERIFIED`;
  marketplace collectors remain disabled until source permissions are reviewed.

```text
SearXNG discovery: LIVE_VERIFIED (one local smoke query, 5 parsed results)
Product/offer data: LIVE_NOT_VERIFIED
Collector: disabled; no marketplace product page was fetched
Verification status: OFFLINE_TESTED + LIVE_VERIFIED discovery
```

### Guest history privacy checkpoint - October 29, 2026

- [x] Reproduced cross-browser history disclosure before the fix: guest B's history included guest A's private query and B could read A's session detail (HTTP 200).
- [x] Added a persistent anonymous guest cookie (`HttpOnly`, `SameSite=Lax`, production `Secure`) mapped to an existing `User` row using a derived identifier; the bearer token itself is not stored in the database. No schema migration or mandatory login was added.
- [x] Enforced ownership checks for session history, search, recommendations, comparisons, feedback, and session-bound product reads. Legacy sessions with no owner remain stored but are hidden from guest history and inaccessible to new guests.
- [x] Two-browser regression verifies guest A can read their session while guest B sees an empty history and receives HTTP 404 for A's history detail, search result, and recommendations; a legacy unowned-session test verifies the row is retained and hidden.
- [x] Backend full suite: `pytest -x --tb=short` - 1030 passed. Frontend: `npm test` - 64 passed; `npm run lint` and `npx tsc --noEmit` passed. Playwright: `npm run test:e2e` - 20 passed. Production build: `npm run build` passed. `git diff --check` completed with exit code 0 (only line-ending notices).
- [ ] Clearing browser site data, using a different browser/device, or closing a private session removes the guest credential; stored history is not deleted but cannot be recovered without that credential. Account-based recovery is outside the approved no-login design.
- [ ] Public deployment remains `NOT_VERIFIED`; this change isolates guest history but does not add API rate limits or complete a public security review. Live provider behavior remains `LIVE_NOT_VERIFIED`.

```text
Verification status: OFFLINE_TESTED
Guest history isolation: OFFLINE_TESTED
Live status: LIVE_NOT_VERIFIED
```

### Product freshness presentation checkpoint - October 29, 2026

- [x] Stale offers already carried a `STALE` status, but their price and availability were visually presented without a nearby explanation. Product cards now label both as `Giá và tình trạng lần cuối ghi nhận` when the offer is stale.
- [x] Frontend regression coverage: `npm.cmd run test:e2e -- e2e/shopping.spec.ts` - 5 passed; full `npm.cmd run test:e2e` - 21 passed. `npm.cmd test` - 64 passed; `npm.cmd run lint`, `npx.cmd tsc --noEmit`, and `npm.cmd run build` passed.
- [x] Backend query/product regression subset: `.venv\Scripts\python.exe -B -X utf8 -m pytest tests/unit/test_requirement_analyzer.py tests/unit/test_hard_filter.py tests/unit/test_product_image_recovery.py tests/unit/test_progressive_retrieval.py tests/integration/test_recommendation_pipeline.py tests/integration/test_products_api.py -q` - 123 passed.
- [x] `git diff --check` completed with exit code 0; Git emitted only existing LF-to-CRLF notices.
- [ ] Live product coverage and freshness remain `LIVE_NOT_VERIFIED`; collector stays disabled pending an approved source registry and source-specific permission review. This UI label does not make stale data current.

```text
Verification status: OFFLINE_TESTED
Live status: LIVE_NOT_VERIFIED
```

### SearXNG adapter hardening checkpoint - October 29, 2026

- [x] Added isolated unit regressions for malformed JSON shapes and invalid
  result URLs. Before the fix, the new tests reproduced 4 failures, including
  leaked `AttributeError`/`TypeError` and valid results being lost when the
  raw provider list contained invalid URLs.
- [x] The adapter now reports malformed response shapes as a sanitized
  `SearchProviderError`, filters non-HTTP(S), malformed, and credential-bearing
  result URLs, validates image URLs, and applies the result limit after
  filtering.
- [x] Targeted command: `python -B -X utf8 -m pytest
  tests/unit/test_searxng_provider.py tests/unit/test_multi_search_provider.py
  -q` - 6 passed. Full isolated backend command: `python -B -X utf8 -m pytest
  -x --tb=short` - 1034 passed. Both processes completed with exit code 0.
- [x] `git diff --check` completed with exit code 0; only line-ending notices
  were emitted. Existing staged trace deletions, local database files, and
  unrelated working-tree edits were preserved.
- [ ] Live provider behavior remains `LIVE_NOT_VERIFIED`: no SearXNG query,
  marketplace crawl, or paid provider request was made. The SearXNG endpoint is
  not configured, and collector permission/source review remains outstanding.

```text
Verification status: OFFLINE_TESTED
Live status: LIVE_NOT_VERIFIED
```
