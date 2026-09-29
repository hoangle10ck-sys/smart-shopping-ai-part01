# Live direct-offer recovery — offline validation

Ngày kiểm tra: 2026-09-28. Branch: `feature/live-search-performance`.
Tiếp tục WIP hiện có; không reset/undo/restore/checkout/clean/commit/merge/tag, không gọi Live API, không sửa UI hoặc database thật.

## A. Files changed

Phần direct-offer recovery được hoàn thành trong các file sau (bao gồm fixture/test WIP được giữ lại):

| File | Nội dung |
| --- | --- |
| `backend/app/core/config.py` | Cấu hình giới hạn thời gian page/domain |
| `backend/app/services/extraction/search_metadata_validator.py` | Identity có fetched page evidence; giữ kiểm tra giá và variant |
| `backend/app/services/extraction/category_evidence.py` | Family Redmi Note từ verified page evidence |
| `backend/app/services/extraction/product_discovery.py` | Extract child URLs thực, có giới hạn |
| `backend/app/services/extraction/product_page_validator.py` | Thu thập product-card links và child seeds của listing |
| `backend/app/services/extraction/product_image_resolver.py` | Đo riêng fetch và verification trong pool hiện tại |
| `backend/app/services/search/progressive_retrieval.py` | Child queue, alternate merchant, domain budgets/cancellation, diagnostics |
| `backend/app/services/search/retrieval_diagnostics.py` | Nhận diện đường dẫn editorial `/hoi-dap/` |
| `backend/app/services/search/cached_search_service.py` | Retrieval version 5 và budget configuration trong cache key |
| `backend/app/services/performance.py` | `page_fetch_ms`, `verification_ms` |
| `backend/tests/fixtures/live_direct_offer_d082d501.json` | Evidence/diagnostics đã lưu của session, không phải HTML tải mới |
| `backend/tests/unit/test_direct_offer_recovery.py` | 24 regression cases |
| `backend/tests/integration/test_direct_offer_recovery_api.py` | 2 cases xuyên pipeline và GET snapshot |
| `docs/LIVE_DIRECT_OFFER_RECOVERY_REPORT.md` | Báo cáo này |

Git còn chứa WIP của các lượt trước: 43 file modified/untracked tổng cộng, không quy toàn bộ diff thành thay đổi của lượt này. Không đổi database schema, API routes, frontend routes, scoring weights hoặc dependencies. Diagnostics là JSON bổ sung trong snapshot hiện có, không backfill snapshot cũ.

## B–C. V60/V50 identity và variant safety

Root cause: so khớp title với URL slug yêu cầu đầy đủ token variant, dù H1 tải từ chính trang đã xác nhận model. URL V60 thiếu `5G`; URL V50 thiếu RAM/storage.

Ngoại lệ mới chỉ áp dụng khi `page_fetched=true`, H1 đầy đủ khớp title, base model khớp URL và không có token xung đột. Nếu có final evidence URL thì hostname/path phải cùng trang. Chỉ capacity/connectivity được phép thiếu trong URL. Metadata chưa fetch vẫn dùng điều kiện cũ.

Giữ reject khác model, Pro/Lite, 4G/5G và capacity như 8GB/256GB so với 12GB/512GB. Chuẩn hóa prefix `Điện thoại` và cụm model lặp ở cuối chỉ khi giữ nguyên tập token identity; không xóa token variant xung đột. Hàm `same_identity` dùng chung không bị nới.

## D. Redmi Note category

Root cause nằm ở category evidence ban đầu, không phải persistence. Bổ sung nhận diện family có số `Redmi Note <n>` hoặc `Xiaomi Redmi Note <n>` trong evidence của page đã verified. Explicit taxonomy/accessory vẫn được ưu tiên; taxonomy mâu thuẫn vẫn reject. Không suy category từ merchant domain hoặc requirement.

Integration kiểm tra evidence -> raw -> normalized/persisted Product -> candidate -> filtering -> GET snapshot. InStock được recommend; OutOfStock bị loại tại availability, không còn bị loại nhầm vì category unknown.

## E–F. Child discovery và alternate merchant

Extract URL thực từ JSON-LD ItemList hoặc product-card anchor. Chỉ nhận URL HTTP(S) cùng origin có hình dạng product, có tên, không localhost/private literal IP; resolver vẫn kiểm tra DNS/public address. Không tạo URL từ tên. Tối đa 12 child seeds/page, child queue giới hạn bởi candidate cap, dùng chung page/domain semaphores và tổng request budget.

Listing cha vẫn unverified. Child phải tải và xác minh độc lập; kết quả được gắn lại query cha để extraction không bỏ sót. Tests cap 1/2 chứng minh không vượt quota, không fetch trùng và không phát minh child thiếu URL.

OutOfStock không tính target. Model đã quan sát là hết hàng được ưu tiên exact-model lookup ở merchant khác, tránh merchant đã thất bại. Hai model hết hàng có thể lần lượt nhận continuation; vẫn giới hạn hai quoted-model attempts, query/page/deadline và no-progress hiện có. Evidence/article metadata có thể gợi model, không chiếm product slots.

## G. Slow-domain và resource handling

Không blacklist `chuyensidienthoai.vn` hoặc merchant cụ thể.

- Default mỗi page: tối đa 4 giây trong retriever, gồm resolver work.
- Default mỗi domain: tối đa 6 giây active wall time cộng dồn trong retrieval; không cộng hai lần khoảng request chạy đồng thời.
- Connect timeout của shared client tối đa 2.5 giây; read timeout hiện có tiếp tục được giữ bên trong giới hạn tổng page.
- Global page concurrency 4, per-domain 2, query concurrency 2 theo default; các setting vẫn bị clamp.
- Sau lỗi, request đang chạy giữ chỗ retry còn lại; không để các timeout lệch nhau tiếp tục nhận request mới trước khi ghi nhận lỗi thứ hai.
- Page không được chạy do hết budget được ghi rõ `resource_budget`, không giả là đã fetch hoặc verified.
- Cancellation giải phóng work accounting/semaphores; shared HTTP client được đóng bằng async context, kể cả timeout/cancellation.
- Deterministic merge theo query/source order; tổng page/query/candidate budgets và no-progress được giữ.

Tests slow domain dùng mock chờ cancellation; merchant nhanh vẫn tạo offer. Test riêng giới hạn active time ngay cả khi trang trả thành công nhưng không có offer. Đây là kiểm chứng offline về giới hạn, không phải số đo latency Live sau sửa.

## H. Timing diagnostics

GET `/api/search/{session_id}` tiếp tục đọc `retrieval_diagnostics[-1].performance` từ snapshot đã persist. Có provider time, `page_fetch_ms`, `verification_ms`, round durations, provider calls, page attempts, stop reason, domain budgets và child URLs.

`page_fetch_ms`/`verification_ms` là tổng thời gian công việc; fetch chạy đồng thời có thể chồng lấp. `product_verification_ms` là thời gian batch gồm chờ. Không cộng các số này để suy ra total wall time. Snapshot cũ thiếu field mới được giữ nguyên; không diễn giải số 0 của request analysis riêng thành độ trễ analysis thực bằng 0.

## I. Fixture before/after

Session lịch sử `d082d501-b0b2-46cf-8f4e-14a5007d0107`: total ~40.45s, provider ~11.85s, page verification batch ~24.71s, round cuối ~16.92s. Những số này là lịch sử, không phải benchmark sau sửa.

| Case | Trước | Sau / giới hạn chứng minh |
| --- | --- | --- |
| V60/V50 observations đã lưu | Reject identity | Identity PASS; vẫn reject giá promo/nhiều giá mơ hồ |
| V60/V50 với fetched H1 và một giá cùng nguồn, fixture kiểm soát | Identity gate reject | 2/2 `VERIFIED_SEARCH_METADATA`, giá 9.000.000 VND trong fixture |
| Redmi Note verified page không ghi literal phone category | Category unknown | Category điện thoại xuyên pipeline |
| Redmi fixture InStock / OutOfStock | Unknown-category gate | 1 / 0 recommendation; OutOfStock reject đúng availability |
| Listing với 2 child links và 1 tên không URL | Không có child queue | 2 child được verify, 3 page requests gồm parent; cap 1 chỉ chạy 1 child |
| Slow/failing domain | Có thể chiếm nhiều lượt chờ | Page/domain budget và retry gate; cancellation không giữ task active |

Không dùng HTML dựng cho tests làm bằng chứng rằng page Live đang bán ở giá đó. Hai offer đã verified trong session lịch sử đều hết hàng; sửa identity/category không tự biến chúng thành hàng còn bán. Các direct URL viettablet/TGDD V30e/mobilecity/dienthoaihay được cấp verification budget nhưng không được tự chứng nhận nếu thiếu giá cụ thể hoặc proof không nhất quán.

## J–O. Validation thực chạy

| Lệnh | Kết quả |
| --- | --- |
| `.venv/Scripts/python.exe -B -X utf8 -m pytest` từ backend | **602 collected, 602 passed, 0 failed, 0 errors, 2 warnings**, 45.33s |
| `npm test` | **41 passed, 0 failed**, 0 skipped/cancelled |
| `npm run lint` | **PASS**, 0 errors / 0 warnings |
| `npm run build` | **PASS**, compile, TypeScript và prerender thành công |
| `npm run test:e2e` | **15 passed, 0 failed**, 43.7s, retries 0 |
| `git diff --check` | **PASS**, exit code 0; chỉ có LF/CRLF notices |

Backend warnings: 1 Starlette/httpx deprecation; 1 PytestCacheWarning do quyền ghi `.pytest_cache`. Không có unclosed client/session warning. Frontend unit có Node `MODULE_TYPELESS_PACKAGE_JSON` warning; E2E có `NO_COLOR`/`FORCE_COLOR` warning và npm update notice, không nâng dependency.

Backend dùng SQLite tạm và tạo schema tự động. E2E dùng Demo backend/database tạm, blank provider keys và chặn external socket connections. Sau E2E không còn listener ở hai port test 13000/18000. Không chạy paid search/API thật.

Full regression bao gồm search failure giữ recommendations/warnings/snapshot; category, requirement values, weight/analyzer/budget; snapshot historical price; structured evidence; 2/3/5 recommendation supply; deterministic merge; pooling/cancellation; old-version/target=1 cache không che target=5; HARD_MAX/FLEXIBLE_TARGET/RANGE tách biệt. Cache version tăng lên 5 để tránh dùng kết quả retrieval cũ; budget settings mới tham gia key, không sửa dữ liệu cache/snapshot lịch sử.

## P. Remaining limitations

- Chưa chạy Live acceptance mới theo yêu cầu; chưa xác nhận thời gian Live mới hoặc số recommendation Live tăng lên.
- Historical V60/V50 snippets vẫn thiếu một giá offer đủ rõ; stock lịch sử vẫn hết hàng. Không nới validator để tạo recommendation.
- Child extraction chỉ hỗ trợ ItemList/product-card links quan sát được, cùng origin. Không render JavaScript hay crawl sâu không giới hạn.
- Giới hạn 4s/page, 6s/domain có thể bỏ qua merchant chậm nhưng hợp lệ; diagnostics ghi rõ skip và settings cho phép điều chỉnh có kiểm soát.
- Thời gian provider, image probes và công việc khác vẫn chịu các giới hạn hiện có; 6s/domain ở đây áp dụng cho page inspection, không phải cam kết tổng search hoàn thành trong 6s.

Kết luận áp dụng cho source fix và automated/offline validation, không thay thế Live acceptance.

**LIVE DIRECT-OFFER RECOVERY FIX = PASS**
