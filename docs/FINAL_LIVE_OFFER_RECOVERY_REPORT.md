# Final Live Offer Recovery — fixture/regression completion

Branch: `feature/live-search-performance`. Kiểm tra ngày 2026-09-28.
Không gọi Live API; không reset/undo/restore/checkout/clean/commit/merge/tag. Báo cáo tiếp tục WIP hiện có.

## A. Files changed

Phần final recovery nằm trong các file sau; các diff khác của phase trước được giữ lại:

Trạng thái cuối: **48 file modified/untracked** gồm **22 tracked modified + 26 untracked**, không có staged changes. Đây là tổng WIP nhiều lượt, không phải 48 file mới sửa ở phase này.

| File | Nội dung |
| --- | --- |
| `backend/app/services/search/progressive_retrieval.py` | Priority tiers, progress, same-merchant duplicate, recovery/broad/alternative scheduling |
| `backend/app/services/search/model_hints.py` | Numeric-leading model, storage, mixed-brand boundary |
| `backend/app/services/search/retrieval_diagnostics.py` | Editorial URL allocation |
| `backend/app/services/search/cached_search_service.py` | Retrieval cache version 6 |
| `backend/tests/unit/test_final_offer_recovery.py` | 19 regression cases cho final recovery |
| `backend/tests/integration/test_candidate_discovery_api.py` | Thêm cache version 5 invalidation case |
| `backend/tests/fixtures/live_final_offer_dfc295bb.json` | Archive 33 sources/session snapshot, xuất read-only, không dựng HTML lịch sử |
| `backend/scripts/audit_final_offer_recovery.py` | Audit/replay offline, không đọc DB hoặc gọi network khi replay |
| `docs/FINAL_LIVE_OFFER_RECOVERY_AUDIT.json` | Từng source, trace hai merchant, historical timings và replay |
| `docs/FINAL_LIVE_OFFER_RECOVERY_REPORT.md` | Báo cáo này |

Không đổi database schema, scoring weights, budget semantics, API routes, frontend routes, UI hoặc dependencies. Không sửa lại category/identity validator đã hoàn thành ở phase trước.

## B. no_progress before/after

Trước: chỉ product identity mới đã verified mới reset `no_progress`. Vì vậy discovery URL/model mới chưa thành offer vẫn có thể bị chặn continuation.

Sau: đếm riêng `new_verified_products`, `new_direct_urls`, `new_child_urls`, `new_model_hints`, `new_merchant_domains`. URL direct/likely product thực mới và child thực mới có thể giữ discovery tiếp tục. Generic landing alias mới tại cùng merchant, không model mới, không được giả là direct-URL progress. Duplicate của variant đã verified hết hàng không reset progress.

Hết ba round không có progress sau ít nhất hai merchant/alternative attempts thì dừng; có một cơ hội bounded cho model thay thế chưa thử sau OOS recovery. Query/page caps và deadline luôn giới hạn cơ hội đó. Test URL generic mới liên tiếp dừng `no_progress`; test direct URLs mới liên tiếp dừng ở `query_budget`, vẫn 0 offer khi chưa có proof.

## C. Direct URL priority before/after

Trước: domain interleaving có thể đưa listing/article hoặc URL chỉ có từ khóa thương mại lên trước product cụ thể. WIP đầu tiên còn xếp generic thương mại trước child đã extract.

Sau: exact/direct product-shaped URL -> likely product có model hint -> child URL thực -> generic commercial/listing. Article/news/review/video được giữ làm metadata, không tranh lượt fetch product. Diversity chỉ áp dụng bên trong cùng tier. Priority chỉ quyết định thứ tự fetch, không xác minh offer. Không hardcode merchant hoặc phát minh URL.

## D. Same merchant/variant duplicates

Chỉ bỏ qua alias khi có proof đã verified của cùng identity/variant, cùng normalized merchant domain và OUT_OF_STOCK trong retrieval hiện tại. Không fetch thêm alias đó, ghi `unavailable_duplicate` và `page_requested=false`. Variant khác hoặc merchant B không bị loại bởi điều kiện này. URL trùng vẫn dùng dedup có sẵn.

Model progress lưu `attempted_domains`; scoped continuation không lặp lại cặp model/merchant đã thử hoặc merchant đã có offer hết hàng. Lookup grouping không thay catalog/offer identity.

## E. Model hints

- Redmi Note 13 Pro 5G 8GB **256GB** không còn bị cắt storage tại giới hạn năm token; phần mở rộng vẫn bounded và chỉ cho capacity tokens.
- `Xiaomi 15T` được nhận. Không nới sang numeric price/budget đơn thuần.
- Boundary Poco chặn tên trộn `vivo X200 Pro Mini Poco X8` thành một model.
- Capacity/connectivity grouping tiếp tục dùng cho phân bổ lookup; giá và variant cuối vẫn phải có direct proof riêng.
- Exact queries có Vietnam/VND context khi requirement dùng ngân sách VND; không thêm toàn bộ prose yêu cầu vào quoted model.

## F–H. Exact recovery, broad fallback và alternatives

Ưu tiên một merchant khác cho mỗi model đã xác minh hết hàng. Khi đã biết OOS, không tiếp tục chuỗi broad commerce/dealer discovery cũ trước recovery.

Nếu direct recovery chưa đủ: giữ **một** bounded category/budget query tại merchant mới, rồi thử model thay thế đã quan sát. TV regression được giữ nguyên: vẫn có budget/category recall, intent, alternative model và merchant diversification. Không sửa test TV để bỏ yêu cầu này.

Fixture chứng minh merchant A OOS, merchant B InStock -> B eligible, dừng target. Fixture exact recovery thất bại -> `Xiaomi 15T` có thể được thử và chỉ thành eligible sau direct page verification. Evidence/article không trở thành final candidate.

## I. V50/V60 safety

V50 lịch sử đã `identity_match=true`, nhưng snippet chỉ nói giảm 300K/tặng voucher, không có giá sản phẩm cụ thể. Giữ reject.

Tests kiểm tra concrete JSON-LD Offer và explicit main-product visible current price; không lấy crossed-out old price, unrelated accessory promo, AggregateOffer range hoặc mixed prices. Một giá cùng nguồn + identity hợp lệ có thể đạt VERIFIED_SEARCH_METADATA theo rule hiện có.

V60 có direct URL, fetched H1 và một Product discovery record, nhưng archived proof không chứa concrete price. “So sánh” là nguyên nhân metadata fallback báo editorial; chưa đủ chứng cứ để nói đó là valid-offer false-negative. Clean fetched Product/H1/concrete price được ưu tiên trước contaminated snippet và đạt VERIFIED_CONTENT; thiếu proof vẫn reject. Không sửa/nới validator chung, không suy giá từ discount.

## J. Latest archive và recovery trace

Session: `dfc295bb-0cef-41b3-83b5-7c1bb1d46335`.
Query: “Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu”.

| Nhóm source (không chồng lấp) | Số |
| --- | ---: |
| Article/news/review/video | 22 |
| Listing/category | 3 |
| Direct verified product | 2 |
| Direct-looking chưa verified | 6 |
| Tổng | 33 |

Hai verified candidates là vivo V30E 12GB/256GB (10.490.000 VND) và Xiaomi Redmi Note 13 Pro 5G 8GB/256GB (6.290.000 VND), đều CellphoneS và OUT_OF_STOCK. 0 eligible/0 recommendations là đúng với proof đó.

Phân bố rejection lịch sử do pipeline ghi (phân loại theo stage, khác phân loại shape phía trên): non-product 21, missing price 5, availability 2, fetch failure 2, identity 1, other 2 = 33. Có thêm **12 provider rows trùng** trong 45 rows/9 queries, không phải 12 source độc lập ngoài 33.

| Model | Alternate query thực đã chạy | Results / direct-looking được fetch | Vì sao không thành offer |
| --- | --- | --- | --- |
| V30E | `site:thegioididong.com "vivo V30E 12GB 256GB" giá bán Việt Nam VND` | 5 results; 2 direct-looking V60/V50, 1 listing được fetch; 2 hỏi-đáp giữ metadata | V60 discovery-only/snippet contaminated; V50 thiếu giá. Listing thiếu identity. Không trả một offer V30E in-stock |
| Redmi Note 13 Pro | `site:mobilecity.vn "Redmi Note 13 Pro 5G 8GB" giá bán Việt Nam VND` | 5 results; 1 direct-looking được fetch, 4 news metadata | Direct page trả bản Pro **4G** và chưa có concrete price; không phải proof cho variant 5G yêu cầu |

V30E hint có tạo, sau hai quoted attempts là exhausted. Redmi Pro hint có tạo nhưng bị cắt storage; sau một scoped attempt vẫn unavailable. Dừng chung `no_progress`, không phải domain time budget. V30E direct URL TGDĐ trong vòng model discovery trước đó cũng đã được fetch nhưng thiếu concrete price.

Không có archived proof đủ để kết luận một valid in-stock offer chắc chắn bị bỏ sót trước candidate stage. File audit JSON có đầy đủ URL/reason/requested/fetched của từng source; fixture không bị sửa để tạo recommendation.

## K. Cache

`retrieval_version=6`. Integration test ghi một cache entry version 5, chứng minh hit trong scope cũ, sau đó scope hiện tại phải gọi retrieval lại. Các test target=1 vs target=5, old version 2, TTL, snapshot price compatibility và budget modes vẫn được giữ. Không migration/backfill database.

## L. Diagnostics và latency safety

Giữ rounds, exact queries, provider calls, page attempts/timings, model states, attempted/failed domains, new URLs/children/models/merchants và stop reason. Tên stop reasons hiện có: `target_reached`, `time_budget`, `query_budget`, `candidate_budget`, `page_budget`, `no_progress`. GET tiếp tục đọc diagnostics từ snapshot; không đưa debug mới lên UI.

Latest historical timings:

| Metric | Giá trị |
| --- | ---: |
| Total search | 31.80565s |
| Provider search | 20.376868s |
| Verification batch wall time | 7.567347s |
| Tổng page-fetch work | 10.816035s |
| Tổng verification work | 2.554750s |
| Rounds / provider calls / page attempts | 6 / 9 / 15 |
| Pages fetched | 13 |
| Domain active time lớn nhất | ~2.618s, dưới budget 6s |

Fetch/work time có thể chồng lấp; không cộng với batch wall time. Provider chiếm phần lớn thời gian session này. Không đo Live mới hoặc tuyên bố latency mới từ replay.

Giữ page budget 4s, domain active budget 6s, shared client/cancellation, concurrency mặc định query 2/page 4/domain 2 và caps hiện có. Không tăng deadline để lấy thêm offer.

## M–S. Validation

| Mục | Kết quả thực chạy trên source cuối |
| --- | --- |
| M. Targeted (10 file retrieval/model/TV/cache/diagnostics) | **163 passed, 0 failed, 2 warnings**, 34.71s |
| N. Backend `.venv/Scripts/python.exe -B -X utf8 -m pytest` | **622 collected, 622 passed, 0 failed, 0 errors, 2 warnings**, 54.99s |
| O. `npm test` | **41 passed, 0 failed**, không skipped/cancelled |
| P. `npm run lint` | **PASS**, 0 errors / 0 warnings |
| Q. `npm run build` | **PASS**, compile/TypeScript/prerender hoàn tất |
| R. `npm run test:e2e` | **15 passed, 0 failed**, 42.2s, retries 0 |
| S. `git diff --check` | **PASS**, exit 0; chỉ có thông báo LF/CRLF |

Hai backend warnings: Starlette/httpx deprecation và quyền ghi `.pytest_cache`. Không có unclosed client/session warning. Frontend unit có Node MODULE_TYPELESS_PACKAGE_JSON warning; E2E có NO_COLOR/FORCE_COLOR warning, không phải lint/test failure. Không nâng dependencies để che warnings.

Backend dùng SQLite tạm tạo schema tự động. Frontend E2E dùng Demo backend/database tạm và chặn external network, không dùng API trả phí hoặc database thật. Sau E2E kiểm tra không còn listener tại 13000/18000. Không chạy lại frontend vì các sửa cuối chỉ ở Live retriever/tests/diagnostics, không đổi frontend hoặc Demo branch.

Regression giữ nguyên: TV broad recall, 3/5 early target, availability/category/scoring/budget, cache/snapshot compatibility, failed refresh giữ recommendations/warnings, timeout/cancellation/pool/concurrency. Lần full 618 test từng phát hiện TV regression và đã được sửa ở source, không làm yếu test; 618/620 không được dùng làm số tổng cuối.

## T. Remaining limitations / replay

- Archive thiếu original HTML và provider responses cho các query mới. Replay trả rỗng cho query chưa có trong archive, không giả lập offer in-stock thành dữ liệu Live.
- Replay mới vẫn 0 eligible; một số query/model thay đổi nên nó không tái hiện đủ hai candidates lịch sử. Đây không phải so sánh recall trên cùng bộ provider responses đầy đủ.
- Fixture kiểm soát chứng minh recovery/priority đúng, không chứng minh merchant Live hiện có hàng hoặc giá mới hợp lệ.
- URL priority/model hints là heuristic phục vụ discovery. Final offer vẫn cần validator và hard filters hiện có.
- Không có Live acceptance mới trong phase này. Dừng để người dùng chạy đúng một acceptance cuối.

**FINAL LIVE OFFER RECOVERY FIX = PASS** — kết luận cho source fix và automated/fixture validation, không tuyên bố Live acceptance đã PASS.
