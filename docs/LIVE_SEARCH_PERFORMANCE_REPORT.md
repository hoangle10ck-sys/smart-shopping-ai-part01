# LIVE SEARCH PERFORMANCE PHASE

Ngày validation: 2026-09-25. Branch: `feature/live-search-performance`.
Tiếp tục working tree đang dở, không reset/undo/restore/checkout/commit/merge/tag.

## A. Files changed

File đã sửa (14):

- `backend/app/api/routes/requirements.py`
- `backend/app/api/routes/search.py`
- `backend/app/core/config.py`
- `backend/app/services/extraction/product_image_resolver.py`
- `backend/app/services/extraction/product_page_validator.py`
- `backend/app/services/llm/client.py`
- `backend/app/services/llm/explanation_service.py`
- `backend/app/services/llm/query_generator.py`
- `backend/app/services/llm/requirement_analyzer.py`
- `backend/app/services/recommendation/recommendation_service.py`
- `backend/app/services/search/cached_search_service.py`
- `backend/app/services/search/progressive_retrieval.py`
- `backend/app/services/search/search_service.py`
- `backend/tests/integration/test_search_cache_api.py`

File mới (6):

- `backend/app/services/performance.py`
- `backend/scripts/benchmark_live_search.py`
- `backend/tests/unit/test_live_search_performance.py`
- `backend/tests/integration/test_live_performance_api.py`
- `docs/LIVE_SEARCH_PERFORMANCE_BENCHMARK.json`
- `docs/LIVE_SEARCH_PERFORMANCE_REPORT.md`

Không sửa frontend, dependency, routes, schema database, `.env` hoặc database thật.

## B. Root causes và audit source đang dở

- Default target=1 khiến vòng tìm kiếm dừng sớm; top_k vốn đã là 5.
- Gemini retry mọi lỗi ở application; requirement client chưa khóa retry ngầm của SDK.
- Analyzer bắt buộc purpose dù category, budget và criteria đã đủ.
- Concurrency/fetch riêng từng query cho phép URL trùng chạy đua trước khi cache nội bộ có kết quả.
- Mỗi page/image mở HTTP client riêng; body HTML bị cắt sau khi tải toàn bộ.
- Cache key chưa chứa target/candidate budget; dữ liệu target=1 có thể được dùng lại.

Khi tiếp tục: các thay đổi target/fail-fast/retrieval đã có; tests/benchmark và cache diagnostics chưa hoàn tất. Test mới có lỗi fixture (query thực tế được nối intent, SearchResult là dataclass, EvidenceReport cần breakdown). Pool đọc HTML đang dở có nguy cơ giải nén hai lần. Đã sửa, bổ sung regressions, rồi chạy toàn bộ suite.

## C. Gemini optimization

503/UNAVAILABLE, 429/RESOURCE_EXHAUSTED được nhận qua status/code hoặc exception cause. Gemini fail-fast sau một application attempt, không backoff overload. SDK `HttpRetryOptions(attempts=1)` và transport timeout rõ ràng. Lỗi khác vẫn dùng retry hữu hạn hiện có; không chuyển mọi exception thành overload.

Fallback provider/local parser giữ nguyên. Explanation bỏ qua provider đã overload trong cùng instance của một recommendation run, không gọi lại năm lần cho năm sản phẩm. Run mới vẫn có thể thử lại. Có test thực sự đi qua mock Gemini SDK: một generate, một close, timeout 2000 ms, SDK attempts=1; kiểm tra cả trường hợp invalid response vẫn retry 3 lần.

Exception body của Gemini không được ghi vào log mới; search warning giữ error kind thay vì chép nguyên exception có thể chứa thông tin nhạy cảm. Các test kiểm tra placeholder bí mật không xuất hiện trong log.

## D. Clarification optimization

Với “Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu”: local parser/fallback có category điện thoại, budget 10 triệu và camera/battery requirements. Analyzer không hỏi purpose khi đã có criteria có name/value. Không tự thêm purpose để qua validation. Budget semantics vẫn được Python suy ra thành FLEXIBLE_TARGET.

Input thiếu category/budget, hoặc chỉ “Điện thoại 10 triệu” chưa có purpose/criteria, vẫn clarification. Query generation và các vòng retrieval giữ intent/budget; scoring tiếp tục deterministic bằng Python.

## E–F. Search/page concurrency

Giới hạn chung cho mọi query trong **một execution**: 2 provider calls, 4 page verification jobs, tối đa 2 verification jobs cho cùng domain đầu vào. Không phải semaphore toàn process cho tất cả người dùng. Có hard clamps và deadline; image probes cũng chạy theo batch hữu hạn và giới hạn domain.

HTTP pool sống trong một retrieval, dùng chung page/image client, đóng qua async context kể cả cancellation. Connect timeout tối đa 2,5 giây; timeout page request theo config, clamp 2,5–4 giây. Manual redirect/public URL checks được giữ; HTML có cap 2 MB decoded bytes, image kiểm tra định dạng/size theo code hiện có. Test kiểm tra gzip, oversize, cancel, timeout, close.

Kết quả provider được merge theo thứ tự query đã chọn; priority fetch theo nguồn, merchant và model. Completion order không quyết định thứ tự source. Có regression đảo độ trễ giữa query để so sánh kết quả.

## G. Dedup fetch

URL được trim/kiểm tra theo SourceFilter hiện có, rồi dedup trước khi schedule fetch. Cùng URL qua nhiều query chỉ inspect một lần mỗi execution. Không tự xóa query string, gộp variant URL hoặc suy diễn canonical URL có thể làm nhầm offer. Khi một candidate từ vòng trước được verify ở vòng sau, nó vẫn được gắn vào query gốc để extraction không mất offer.

## H–I. Adaptive retrieval và recommendation count

Default/effective config đã kiểm tra an toàn: target=5, minimum=3, top_k=5, query limit=12, results/query=5. Không còn hidden target=1 trong runtime code. Explicit target override vẫn được hỗ trợ.

- Vòng requirement tối đa 2 query; tiếp tục commercial, observed model, merchant nếu chưa đủ.
- Candidate verification cap ban đầu 10, tăng có giới hạn đến 20. Khi dưới minimum, mở rộng nhiều hơn; khi đã có 3–4 eligible offers, mở rộng từng batch nhỏ.
- Giữ query diversity/model discovery hiện có; xen kẽ merchant/model khi chọn page để fetch.
- Early-stop khi đủ unique **ready** offers theo rule budget và evidence hiện có. OUT_OF_STOCK không count; UNKNOWN availability vẫn eligible.
- Offer thiếu requirement evidence vẫn có thể là kết quả fallback, nhưng không bị tự coi là matched để early-stop. FLEXIBLE_TARGET ngoài preferred window vẫn là fallback hợp lệ, không biến thành hard rejection.
- Dừng hữu hạn bởi target, candidate cap, query cap hoặc time budget. Chỉ 2/3 valid offers thì trả 2/3; fixture đủ 5 trả 5. Không tạo thêm sản phẩm để lấp số lượng.

Giữ dedup identity hiện có; nhiều merchant cho cùng identity không làm tăng ready count. Variant được xử lý theo offer identity/business rules sẵn có. Test pipeline kiểm tra score bằng đúng 25/30/20/10/5/10 và GET giữ recommendation snapshot.

## J. Cache

Scope thêm retrieval_version=2, target, minimum, query limit, time budget, initial/max candidates. Cache budget tiếp tục phân biệt HARD_MAX/FLEXIBLE_TARGET/RANGE. Cache cũ tự miss theo key mới, không migration/delete/backfill; TTL và snapshot semantics giữ nguyên. Không thêm page cache xuyên session có thể giữ giá cũ.

Test cache cũ cấu hình target=1 rõ ràng trong fixture để tiếp tục đo riêng TTL/snapshot. Test integration mới dùng default target=5, kiểm tra cache hit không có provider call và đổi từng retrieval config phải miss.

## K. Diagnostics/timing

Request-local ContextVar, được reset cả khi lỗi; không thêm field bắt buộc/API route. Search POST bổ sung một phần tử `{"performance": ...}` trong `retrieval_diagnostics` vốn là list dictionary. Analyze/clarify ghi log `shopping_performance`; GET lịch sử không gán timing mới vào snapshot cũ.

Timings có: requirement_analysis_ms, clarification_ms, query_generation_ms, search_provider_ms, product_discovery_ms, product_verification_ms, extraction_ms, filtering_ms, scoring_ms, explanation_ms, total_search_ms. Stage không chạy ở request đó bằng 0. Analyze/clarify/search là request riêng; timing có nesting, không cộng tùy tiện thành tổng.

Diagnostics có generated_queries, candidates_found, unique_candidate_urls, pages_verified, rejected_wrong_category/non_product_page/missing_price/out_of_stock/duplicate/other, valid_offers, final_recommendations; thêm cache_hit, candidate_cap, unverified_candidates, stop_reason khi phù hợp.

`candidates_found` là URL duy nhất sau SourceFilter; raw provider result_count vẫn có ở diagnostic từng query. `pages_verified` đếm lượt inspect hoàn tất, bao gồm rejected/blocked, không đồng nghĩa accepted. Rejection là lý do đầu tiên cho từng concrete offer; duplicate gồm URL đã gặp và identity trùng. Vì một page có thể chứa variants, các counters này không phải các phần của một tổng số page duy nhất. Cache hit không bịa fetch/verify mới: final_recommendations có số snapshot, search/verify timing bằng 0.

Validator chỉ thêm `rejection_code=missing_price` ở nhánh từ chối đang có. Không đổi predicate accept/reject hoặc hạ category/evidence safety.

## L. Local benchmark before/after

Chạy `backend/.venv/Scripts/python.exe -B -X utf8 backend/scripts/benchmark_live_search.py` từ root, hoặc bỏ prefix backend của script/interpreter khi đứng trong backend.

Đọc baseline classes qua `git show v1.2.0:...` (commit `b2d9ebc8b7b4c8ac2357f9a84153e1dab7467c4a`), không checkout. Backend giữa tag và HEAD trước sửa không có diff. Median 3 lượt, provider delay 20 ms, page 40 ms, LLM 20 ms; fixtures `.example`, chặn socket network. Raw runs lưu trong [JSON benchmark](LIVE_SEARCH_PERFORMANCE_BENCHMARK.json).

| Retrieval local | Duration ms | Provider calls | Page fetches | Duplicate fetches | Valid offers / recommendations |
|---|---:|---:|---:|---:|---:|
| Before default target=1 | 94.861 | 2 | 4 | 2 | 2 / 2 |
| Before, cấu hình target=5 để so sánh cùng mục tiêu | 268.006 | 4 | 10 | 5 | 5 / 5 |
| After target=5 | 207.074 | 4 | 5 | 0 | 5 / 5 |

Ranking name/price/score ở hai trường hợp target=5 được assert bằng nhau. Gemini overload: before **1587.446 ms / 3 attempts**, after **21.588 ms / 1 attempt**. Tổng tổng hợp từ hai phép đo riêng (LLM overload + retrieval) là **1682.307 → 228.662 ms**, không phải timing một HTTP end-to-end request.

So với default cũ, retrieval riêng lâu hơn vì lấy 5 thay vì 2. Ở cùng target=5, số fetch và thời gian đều giảm trong fixture này. Không tuyên bố mức cải thiện đó cho mạng Live; benchmark không đo SDK-internal retry, DB, browser, human clarification, image tải thật hoặc LLM explanation thật.

## M–Q. Final validation

| Command | Kết quả trên source cuối |
|---|---|
| Backend `.venv\Scripts\python.exe -B -X utf8 -m pytest` | 553 collected / 553 passed / 0 failed; 2 warnings; 30.99 s |
| Frontend `npm test` | 41 tests / 41 passed / 0 failed |
| `npm run lint` | PASS, 0 errors / 0 warnings |
| `npm run build` | PASS, compile + TypeScript + static generation |
| `npm run test:e2e` | 15 / 15 passed, exit code 0; 5.7 phút gồm thời gian chờ teardown |

Backend warnings: Starlette deprecation khi dùng httpx TestClient và PytestCacheWarning do quyền ghi `.pytest_cache`. Không có warning unclosed client. Database là SQLite tạm từ conftest, schema được tạo/đặt lại tự động, không dùng smart_shopping.db. Không cần workaround TEMP lần này.

Frontend test có Node MODULE_TYPELESS_PACKAGE_JSON warning hiện có; E2E có cảnh báo NO_COLOR/FORCE_COLOR. Không sửa dependency/config ngoài phạm vi để dọn các warning này.

E2E: cả 15 scenario hoàn tất trước khi teardown bị kẹt trong sandbox Windows. Sau khi xác minh PID/command line của đúng server `run_e2e_backend.py` và Next port 13000, dừng hai process đó bằng quyền ngoài sandbox; Playwright tự kết thúc và báo `15 passed (5.7m)`, exit 0. Không sửa runner hoặc giết process ngoài lượt test. Thời gian 5.7 phút không phải latency hành trình mua sắm.

31 tests mới: 20 unit + 11 integration. Coverage gồm overload/fallback/SDK attempts, clarification, concurrency/global/per-domain, deterministic merge, duplicate URL/model, adaptive cap/stop, stock unknown/OOS, 2/3/5 recommendations, category/price rejections, cache config và ba budget modes, score/snapshot, request-local timing, pool gzip/size/timeout/cancellation.

Toàn bộ regression cũ vẫn pass: search fail không mất kết quả/warnings/status; category filtering, requirement value matching, weight/analyzer/budget parsing; snapshot price/evidence; Live explanation fallback; History/Cache; structured match/evidence; verified sales/image/category/variant retrieval. Browser suite dùng Demo/local backend và fixtures, external I/O bị chặn.

## R. Git safety

`git diff --check`: PASS (cảnh báo LF→CRLF của Git không phải whitespace error). Branch `feature/live-search-performance`. Working tree giữ các thay đổi chưa commit; không commit, merge hay tag.

## S. Remaining limitations

- Chưa có phép đo paid Live trước/sau; network, quota, blocked merchant và dữ liệu thực có thể làm thời gian/số offer thay đổi.
- Target=5 là mục tiêu, không đảm bảo. Readiness giữ yêu cầu evidence/window cũ nên có thể tiếp tục tìm dù đã có nhiều eligible fallback offers, đến cap/deadline hiện có (default 120 giây).
- Concurrency giới hạn trong một search execution, không thêm process-wide limiter hay request coalescing. Giới hạn domain ở page verification dựa trên domain URL đầu vào; HTTP redirect vẫn bị giới hạn số lần và kiểm tra public URL như trước.
- Connection pooling chỉ trong lượt retrieval; không mở rộng thành cache giá xuyên session. URL dedup dùng URL hiện có, không đoán tương đương giữa các query string khác nhau.
- Benchmark cô lập retrieval/ranking và application retry; không chứng minh latency end-to-end ngoài Internet.

Đã giữ scoring weights, budget semantics, UNKNOWN handling, validator/category safety, Product/Offer separation và toàn bộ routes. Không dùng Demo offers để thay kết quả Live trong test pipeline; fixtures chỉ giả lập nguồn mạng để kiểm tra code Live.

LIVE SEARCH PERFORMANCE PHASE = PASS
