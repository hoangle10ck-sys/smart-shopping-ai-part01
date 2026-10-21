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
- [ ] Offline backend suite, frontend unit/lint/build và Playwright pass; test không gọi Internet/API trả phí.
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
  references; retain only explicit historical notes where useful.
- [ ] Run backend targeted and full tests, frontend test/lint/build, and
  `git diff --check`; record actual command output and resolve failures.
- [ ] Build and run Docker only where Docker Engine is available.
- [ ] Configure at least one authorized live provider and perform opt-in live
  acceptance with timestamp, provider outcome, evidence and persisted counts.
- [ ] Review SearXNG AGPL-3.0 implications before distributing or offering a
  hosted service using a SearXNG deployment.

**Current verified status:** code inspection only; automated checks and live
provider behavior have not yet been confirmed in this checkpoint. No provider
configuration is assumed, and provider coverage is limited to integrations
explicitly configured and permitted by the operator.

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