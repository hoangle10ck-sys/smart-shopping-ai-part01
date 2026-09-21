# Real product images + direct product sales pages — kết quả kiểm tra

Ngày kiểm tra: 14/09/2026. Trạng thái tổng thể: **PARTIAL**. Kiểm thử tự động đạt; ba scenario LIVE chưa chứng minh được recommendation có trang bán hàng và ảnh thật phù hợp. Không coi HTTP 200 với danh sách rỗng là manual PASS.

## A. File sửa/tạo

File sửa:

- `backend/app/api/routes/products.py`
- `backend/app/schemas/product.py`
- `backend/app/schemas/recommendation.py`
- `backend/app/schemas/search.py`
- `backend/app/services/dedup/product_deduplicator.py`
- `backend/app/services/extraction/product_image_resolver.py`
- `backend/app/services/llm/query_generator.py`
- `backend/app/services/normalization/normalization_service.py`
- `backend/app/services/recommendation/candidate_builder.py`
- `backend/app/services/recommendation/recommendation_service.py`
- `backend/app/services/search/base.py`
- `backend/app/services/search/search_service.py`
- `backend/app/services/search/source_filter.py`
- `backend/app/services/search/tavily_provider.py`
- `backend/app/services/validation/structured_evidence.py`
- `backend/tests/integration/test_result_metadata.py`
- `backend/tests/integration/test_search_api.py`
- `backend/tests/integration/test_search_cache_api.py`
- `backend/tests/unit/test_query_generator.py`
- `frontend/app/products/[productId]/page.tsx`
- `frontend/components/product-card.tsx`
- `frontend/e2e/shopping.spec.ts`
- `frontend/lib/api.ts`
- `frontend/lib/results-utils.ts`
- `frontend/types/shopping.ts`

File tạo:

- `backend/app/services/extraction/product_page_validator.py`
- `backend/scripts/check_live_sales.py`
- `backend/tests/fixtures/sales_pages.py`
- `backend/tests/integration/test_verified_sales_pipeline.py`
- `backend/tests/unit/test_product_page_validator.py`
- `backend/tests/unit/test_search_provider_diagnostics.py`
- `frontend/tests/product-links.test.mjs`
- `docs/LIVE_PRODUCT_CHECK.json`
- `docs/REAL_PRODUCT_PAGES.md`

## B. Product page validator

Trước đây URL nguồn tìm kiếm có thể thành URL mua hàng mà chưa kiểm tra nội dung. Nay Live xác minh URL, HTML, tên/model và giá cụ thể cùng nguồn trước khi tạo offer. JSON-LD Product/Offer là nguồn chính; OG hoặc giá HTML có đánh dấu cần kèm hành động mua. Homepage, category, search, bài viết, review, giá tổng hợp/khoảng giá và nội dung sai identity không trở thành offer. Trang nhà sản xuất chỉ có giá đề xuất nhưng không có hành động mua bị loại.

## C. Commercial search query

Giữ truy vấn chứa nhu cầu/ngân sách và bổ sung truy vấn ngắn `{brand/category} mua chính hãng` ở vị trí thứ hai, hoạt động ngay khi cấu hình chỉ cho phép hai query. Dùng category được phân tích, không có nhánh riêng xe máy/TV/điện thoại. Kiểm thử bao gồm category ngoài danh sách thông dụng. Bỏ yêu cầu ảnh tổng hợp và mô tả ảnh từ Tavily vì pipeline không sử dụng chúng để chứng minh identity.

## D. Search result classification

Schema nguồn hỗ trợ `DIRECT_PRODUCT`, `CATEGORY`, `HOMEPAGE`, `SEARCH_PAGE`, `ARTICLE`, `NEWS`, `REVIEW`, `UNKNOWN`. URL chỉ gợi ý phân loại; `DIRECT_PRODUCT` cần chứng cứ nội dung. Metadata Article/NewsArticle/Review/CollectionPage ngăn nhầm Product nhúng trong bài viết thành trang bán hàng. Nguồn không đủ tín hiệu giữ UNKNOWN. Extraction xử lý direct product đã xác minh trước. Nguồn còn lại có thể cung cấp evidence, không có URL/giá mua hàng.

## E. Merchant/offer selection

Giá, URL, merchant và ảnh được gắn với cùng một quan sát offer. Merchant lấy từ seller metadata nếu có, nếu không dùng hostname, không đoán tên cửa hàng. Chọn offer đã xác minh theo tình trạng hàng, giá hợp lệ, độ tin cậy nguồn, freshness, độ đầy đủ specification rồi giá/id. Không đổi trọng số tính score.

## F. Product identity

Đối chiếu tên trang và Product metadata; khi có tên cần kiểm tra lại thì phải cùng identity. Phân biệt model số/chữ, Pro/Max/Plus/Ultra và dung lượng. Dedup không gộp iPhone 15, 15 Pro và các cấu hình dung lượng khác nhau. Quy tắc bảo thủ có thể bỏ sót tên viết tắt/alias; không dùng LLM để quyết định identity hoặc final score.

## G. Image extraction/validation

Ưu tiên ảnh của JSON-LD Product tương ứng, sau đó OG, Twitter và ảnh HTML có alt khớp tên. Không lấy ảnh query-wide thay thế. Chặn URL không HTTP(S), logo/banner/category và dấu hiệu model mâu thuẫn. Kiểm tra public URL, redirect, HTTP status, MIME, chữ ký định dạng raster và giới hạn 5 MB. Ảnh lỗi/timeout để null; không hủy offer đã xác minh. Frontend có placeholder khi ảnh thiếu hoặc tải lỗi. Không thêm dependency xử lý ảnh hay sửa Next remotePatterns vì giao diện hiện dùng thẻ img.

## H. Product URL và evidence URL; tương thích

`product_url` của offer Live mới chỉ có sau khi xác minh trang bán đúng sản phẩm; `evidence_url` lưu nguồn đối chiếu riêng. Nút “Xem sản phẩm” yêu cầu cờ backend xác minh và URL hợp lệ, mở tab mới với `noopener noreferrer`. Nguồn chưa xác minh hiển thị “Xem nguồn”.

Không thêm cột/table SQL, không migration/backfill database thật. Metadata nằm trong JSON raw candidate và snapshot hiện có. API response thêm field tùy chọn và `result_type` với mặc định UNKNOWN. Product detail giữ route cũ, thêm query parameter tùy chọn `session_id` để lấy recommendation snapshot của phiên. Frontend chuyển `sessionId` khi mở detail và ghi rõ giá/score/evidence của phiên khác với catalog hiện tại. Snapshot cũ thiếu metadata vẫn đọc được; không tự gắn bằng chứng mới vào dữ liệu lịch sử. Không đổi TTL/key/cách phục hồi History/Cache.

## I. Backend tests

Lệnh chạy từ `backend`: `.\.venv\Scripts\python.exe -B -X utf8 -m pytest`.

Kết quả cuối: **322 collected, 322 passed, 0 failed, 2 warnings**, 16.54 giây. Warnings: Starlette deprecation cho httpx TestClient; pytest không ghi được `.pytest_cache` do quyền Windows. Database là SQLite tạm, schema tự tạo/xóa bằng fixture hiện có; không dùng `smart_shopping.db`.

Test bổ sung phủ URL/nội dung không phải trang bán hàng, 8 loại nguồn, model/dung lượng và ảnh sai model cùng hãng, ảnh HTTP lỗi/redirect, timeout ảnh vẫn giữ offer, structured decimal price, commercial query generic, Tavily timeout/HTTP 401/503/429/network/malformed/empty response. Integration kiểm chứng hai merchant và giá riêng, extraction ưu tiên direct, evidence bài review, dedup biến thể, session A giá 15 triệu và session B cập nhật 20 triệu nhưng GET A/history/detail vẫn giữ snapshot A. Test Phase 1 còn kiểm tra warning `[timeout]` được giữ khi GET.

Regression Phase 1–7 trong suite đều pass: search failure preservation, category/value scoring/weight/analyzer, snapshot/explanation fallback, History/Cache, structured matching/evidence và luồng Demo. Không xóa hoặc skip test; các mock Live cũ được đổi sang HTML local có dữ liệu trang bán để chạy validator thật.

## J. Frontend tests, lint và build

`npm test`: **32 passed, 0 failed, 0 skipped**. Hai thông báo Node `MODULE_TYPELESS_PACKAGE_JSON` khi import module TypeScript.

`npm run lint`: **PASS, 0 errors, 2 warnings** đã có ở trang compare (useMemo dependency) và Home (window.location navigation).

`npm run build`: **PASS**, production build Next.js 16.3.3 chạy sau E2E; TypeScript và prerender đều hoàn tất, exit code 0.

## K. Browser E2E

`npm run test:e2e`: **4 passed**, 33.1 giây. Demo/local backend, database tạm, các ảnh/API mô phỏng, không gọi provider trả phí. Bao gồm hành trình Home → analyze/search → results → filter/sort → detail/compare → feedback/history; ba trạng thái requirement và evidence; snapshot cũ/warning lỗi; direct sales link và placeholder khi ảnh 404. Playwright có warning NO_COLOR/FORCE_COLOR của môi trường, không có test fail.

## L–N. Manual LIVE

Chạy `backend/scripts/check_live_sales.py` bằng khóa cấu hình trong `backend/.env`, Tavily + Gemini, DB TemporaryDirectory độc lập. Không ghi đè `.env` hoặc in key. Chi tiết response, sources, page_validation, warning qua GET và lần kiểm tra trước nằm trong [LIVE_PRODUCT_CHECK.json](LIVE_PRODUCT_CHECK.json).

| Scenario | Lần kiểm tra cuối | Kết luận |
| --- | --- | --- |
| Xe máy 45 triệu, đi học, tiết kiệm xăng | Analyze 200; Search 200; 0 recommendation. Có homepage, category, video/nguồn UNKNOWN, không có direct product đã xác minh. | **CHƯA ĐẠT** |
| TV 10 triệu, xem phim | Gemini 429 hết quota → analyzer fallback yêu cầu purpose → Search 409 chưa có query. Lần trước khi analyzer chạy được, hai query Tavily đều timeout 10 giây và Search trả 503. | **CHƯA ĐẠT / bị chặn** |
| Điện thoại 10 triệu, camera tốt, pin lâu | Clarification qua API với câu **“chụp ảnh”** trả 200. Search 200; 0 recommendation, nguồn là bài viết/review/category/video. | **CHƯA ĐẠT** |

Không có recommendation LIVE nào để báo NAME / PRICE / MERCHANT / DOMAIN / PRODUCT_URL / PRODUCT_PAGE_VALID / IMAGE_URL / IMAGE_SOURCE / IMAGE_LOADS / EVIDENCE_URL. Các danh sách `recommendations` trong JSON để rỗng; không điền sản phẩm demo hoặc URL tự dựng thay cho bằng chứng thực tế.

## O. Provider failures

Lỗi Tavily trước đó được xác định là timeout theo cấu hình 10 giây/attempt, không phải kết quả rỗng. Sau khi bỏ ảnh tổng hợp, lần cuối không quan sát timeout ở xe máy/điện thoại; chưa đủ cơ sở kết luận đã hết timeout toàn bộ. TV không đến bước Tavily ở lần cuối vì Gemini hết quota và clarification chưa hoàn tất.

Adapter hiện phân biệt `timeout`, `http_error` (kèm HTTP status), `rate_limit` (429), `malformed_response`, `network_error`, lỗi cấu hình. Không đưa body/key vào thông báo lỗi. `results: []` hợp lệ là no results, không thành provider failure. Một query lỗi vẫn giữ partial success; tất cả lỗi giữ FAILED/warnings và snapshot cũ theo Phase 1. Các trường hợp HTTP/malformed dùng mock để xác minh, không khẳng định chúng đã xảy ra ở Tavily LIVE.

Gemini thực tế đã trả 503 high demand và 429 quota exhausted; không tự đổi model, key hoặc quota/config để che lỗi.

## P. Giới hạn thực tế và phạm vi

- Chưa đạt mục tiêu recommendation LIVE có ảnh thật và link mua hàng qua ba scenario; nguồn tìm kiếm vẫn thiên về bài viết/danh mục. Không tự crawl sâu danh mục hoặc thêm provider/kiến trúc mới.
- Không có trình duyệt server để render trang JavaScript/chống bot. Trang không tải/không có đủ metadata hoặc giá biến thể rõ ràng sẽ bị loại.
- Image validation dựa trên metadata, tên/mã model và phản hồi HTTP; không phải nhận dạng nội dung pixel. Ảnh filename mờ nghĩa hoặc metadata của merchant sai có thể cần kiểm chứng thủ công. Không tuyên bố bảo đảm hình ảnh đúng 100%.
- URL/ảnh có thể đổi hoặc hết hạn sau thời điểm kiểm tra; snapshot giữ quan sát cũ, frontend dùng placeholder nếu ảnh về sau hỏng.
- Legacy snapshots không được backfill bằng chứng sales-page. Có thể đọc dữ liệu cũ nhưng không chứng nhận link mua hàng chưa được xác minh.
- Không đổi routes, SQL schema, stack/dependencies, scoring weights; không sửa database thật, History/Cache semantics, Docker/Voice/deployment. Không commit/reset Git.
