# Manual LIVE verification — 15/09/2026

Kết quả tổng thể: **PARTIAL**. Chạy tuần tự đúng ba yêu cầu bằng Tavily và cấu hình `backend/.env` hiện tại. Gemini `gemini-3.6-flash`, fallback local. Không dùng sản phẩm Demo; local fallback chỉ phân tích yêu cầu/giải thích. Database SQLite tạm độc lập; không sửa `.env` hoặc database thật.

Timeout Tavily thực dùng: **10 giây**, không override lên 25 giây. Giới hạn retrieval: 12 query / 120 giây mỗi scenario. `DIRECT_PRODUCT` thể hiện xác minh trang, không đồng nghĩa sản phẩm vượt qua hard filter hoặc có recommendation.

## A–C. Tổng quan ba scenario

| Metric | A | B | C |
| --- | ---: | ---: | ---: |
| Tavily results | 60 | 60 | 60 |
| Unique URLs | 49 | 46 | 48 |
| DIRECT_PRODUCT | 0 | 4 | 2 |
| ARTICLE | 7 | 4 | 6 |
| NEWS | 10 | 3 | 15 |
| REVIEW | 0 | 0 | 1 |
| FETCH_BLOCKED | 11 | 7 | 5 |
| VERIFIED_CONTENT | 0 | 4 | 2 |
| VERIFIED_SEARCH_METADATA | 0 | 0 | 0 |
| Candidates | 0 | 4 | 2 |
| Hard-filter rejected | 0 | 4 | 1 |
| Recommendations | 0 | 0 | 1 |

Số loại nguồn/verification trong bảng cộng theo từng kết quả query (có thể lặp URL). Số nguồn duy nhất được ghi riêng. `Hard-filter rejected` là số bị loại; API `total_filtered` hiện biểu thị số **còn lại sau filter**, không phải số bị loại. `FETCH_BLOCKED` bao gồm lỗi tải, timeout, JS/chống bot; không đồng nghĩa tất cả đều HTTP 403. Đếm theo query có thể chồng giữa loại nguồn và mức verification.

### A. Xe máy

Yêu cầu: “Tôi có 45 triệu, cần xe máy để đi học, tiết kiệm xăng.” Category `xe máy`, budget_max 45.000.000 VND, purpose `đi học`, requirement tiết kiệm xăng.

**0 recommendation.** Sản phẩm bị mất ở bước xác minh page/offer, trước candidate và hard filter. 60 Tavily results; 1 bị source filter loại, 59 lượt nguồn được kiểm tra; không nguồn nào đạt verification.

Đã tải lại ba trang tìm được để kiểm tra nguyên nhân cụ thể:

- `https://hondath.vn/xe-may/xe-so/honda-wave-alpha-110`: H1 và Product identity khớp, nhưng chỉ có `AggregateOffer`, 4 offers, khoảng 17.859.273–18.742.909 VND. Không có một giá/phiên bản đã xác định nên không lấy lowPrice làm offer.
- `https://hondath.vn/xe-may/xe-con-tay/honda-winner-x`: identity khớp, 7 offers, khoảng 46.160.000–50.560.000 VND; không xác định một phiên bản/giá. Khoảng giá này cũng vượt budget.
- `https://phattien.com/san-pham/honda-sh-160i.html`: tải được, H1 `Honda SH160i`; parser không tìm được Product JSON-LD hoặc tín hiệu giá/hành động mua đáp ứng validator hiện tại. Không kết luận trang không bán sản phẩm; kết luận **chưa đủ bằng chứng để tạo offer bằng implementation hiện tại**.

Các nguồn khác bị loại do homepage/category/article/news hoặc metadata không chứng minh title/slug/snippet cùng model. Chi tiết tải lại: [LIVE_PAGE_DIAGNOSTICS.json](LIVE_PAGE_DIAGNOSTICS.json).

### B. TV

Yêu cầu: “Tôi cần TV khoảng 10 triệu để xem phim.” Category `tivi`, budget_max 10.000.000 VND, purpose `xem phim`. Local fallback nhận được mục đích, không bị chặn tại clarification.

**4 candidates, 4 bị hard filter budget loại, 0 recommendation.** Các trang sản phẩm đã qua `VERIFIED_CONTENT`; không bị loại do thiếu ảnh. Giá thấp nhất trong bốn candidates là 12.490.000 VND, vẫn vượt ngân sách. Không nâng budget hoặc sửa filter để ép kết quả.

### C. Điện thoại

Yêu cầu: “Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu.” Category `điện thoại`, budget_max 10.000.000 VND. Clarification được trả lời **“chụp ảnh”** qua API; không bypass.

**2 candidates, 1 bị loại category (là TV), 1 recommendation.** Recommendation còn lại đủ điều kiện về trang bán/giá; thiếu thông số để xác nhận camera tốt và pin lâu. Không được diễn giải là các tiêu chí đó đã được thỏa mãn.

| Field | Value |
| --- | --- |
| NAME | "Điện thoại vision 1 pro 2/32" |
| BRAND | null |
| MODEL | null |
| PRICE | 1390000 |
| MERCHANT | "daidoangia.vn" |
| DOMAIN | "daidoangia.vn" |
| PRODUCT_URL | "https://daidoangia.vn/dien-thoai-vision-1-pro-232" |
| PRODUCT_PAGE_VALID | true |
| VERIFICATION_LEVEL | "VERIFIED_CONTENT" |
| PRODUCT_PAGE_CONFIDENCE | 95.0 |
| IMAGE_URL | null |
| IMAGE_SOURCE | null |
| IMAGE_LOADS | false |
| EVIDENCE_URL | "https://daidoangia.vn/dien-thoai-vision-1-pro-232" |

Đã GET lại đúng URL trên sau khi search. `manual_content_confirmed=true`, `manual_price_matches=true`: giá 1.390.000 VND nằm trong marker giá chính của chính trang, không phải giá của sản phẩm liên quan. URL không chuyển về homepage/category/search/bài viết. Trang có OG image `vivo-y02-den.jpg` mâu thuẫn với tên Vision 1 Pro; backend đã loại ảnh, trả `image_url=null`. Không loại recommendation vì thiếu ảnh. BRAND/MODEL riêng không có dữ liệu tin cậy nên giữ null.

## D. Direct product URLs thực tế

Các URL dưới đây đã được pipeline kiểm tra nội dung trong lần LIVE này. Chỉ dòng Vision là recommendation; các TV không đáp ứng yêu cầu tương ứng. Chúng không phải danh sách gợi ý thay thế cho budget người dùng.

| Product | Merchant | Price (VND) | URL |
| --- | --- | ---: | --- |
| Smart Tivi Samsung QLED 4K 55 inch 2024 (55Q70D) | CELLPHONES | 14490000 | [Product page](https://cellphones.com.vn/smart-tivi-samsung-qled-55q70d-4k-55-inch-2024.html) |
| Smart Tivi Samsung Neo QLED 4K 55 inch 2025 (55QN70F) | CELLPHONES | 13590000 | [Product page](https://cellphones.com.vn/smart-tivi-samsung-neo-qled-55qn70f-4k-55-inch-2025.html) |
| Smart Tivi Samsung OLED 4K 55 inch 2025 (55S85F) | CELLPHONES | 21990000 | [Product page](https://cellphones.com.vn/smart-tivi-samsung-oled-55s85f-4k-55-inch-2025.html) |
| Smart Tivi Samsung QLED 4K 55 inch 2025 (55Q8FA) | CELLPHONES | 12490000 | [Product page](https://cellphones.com.vn/smart-tivi-samsung-qled-55q8fa-4k-55-inch.html) |
| Điện thoại vision 1 pro 2/32 | daidoangia.vn | 1390000 | [Product page](https://daidoangia.vn/dien-thoai-vision-1-pro-232) |

## E. Ảnh thực tế

**Không có image_url được sử dụng trong recommendation cuối.** Vì vậy không có ảnh được công bố là ảnh đúng model trong kết quả này. `IMAGE_LOADS=false` của ảnh null nghĩa là không có URL để tải, không phải một lần HTTP tải ảnh thất bại.

Đã xác định hai loại ảnh không hợp lệ trong dữ liệu trang:

- `https://cdn2.cellphones.com.vn/358x/media/wysiwyg/placehoder.png`: placeholder của merchant, không phải ảnh sản phẩm. Đã bổ sung chặn đúng tên viết thiếu chữ `placehoder`.
- `https://daidoangia.vn//Images/product/2212080350-vivo-y02-den.jpg`: tên ảnh Vivo Y02 khác Vision 1 Pro. Không đưa vào recommendation.

Không tải ảnh query-wide hoặc ảnh sản phẩm khác để thay thế. Các bằng chứng ảnh lịch sử ở `previous_check` trong JSON không được dùng làm kết quả hiện tại.

## F. Provider errors và query diagnostics

Trong lần này Tavily hoàn tất **36/36 query**, mỗi query trả 5 results: không quan sát Tavily timeout/HTTP error/rate limit/malformed response. Không suy diễn rằng provider sẽ luôn ổn định.

Gemini có **503 UNAVAILABLE** và **429 RESOURCE_EXHAUSTED** (quota), thể hiện trong log thực thi. Analyzer/clarification vẫn dùng local fallback; recommendation explanation có `generation_mode=fallback`. Không dùng Gemini để quyết định giá, score hay verification. Không in API key.

Mỗi query và số liệu kiểm tra:

### A - Queries

| Pass | Query | Results | Direct | A/N/R | Blocked | Content | Metadata |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| requirement | xe máy giá dưới 45000000 VND đi học fuel_efficiency tiết kiệm xăng mua giá bán Việt Nam | 5 | 0 | 0 / 4 / 0 | 0 | 0 | 0 |
| requirement | xe máy mua chính hãng | 5 | 0 | 0 / 0 / 0 | 2 | 0 | 0 |
| commercial | xe máy giá bán sản phẩm | 5 | 0 | 0 / 3 / 0 | 0 | 0 | 0 |
| commercial | xe máy mua online | 5 | 0 | 0 / 1 / 0 | 2 | 0 | 0 |
| commercial | site:honda.com.vn xe máy giá | 5 | 0 | 0 / 1 / 0 | 3 | 0 | 0 |
| merchant_discovery | xe máy cửa hàng | 5 | 0 | 0 / 0 / 0 | 2 | 0 | 0 |
| merchant_discovery | xe máy đại lý | 5 | 0 | 0 / 0 / 0 | 2 | 0 | 0 |
| merchant_products | site:honda.com.vn Honda Winner X giá | 5 | 0 | 3 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:hondath.vn Honda Winner X giá | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:hondath.vn xe máy giá | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:phattien.com xe máy giá | 5 | 0 | 3 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:sym.com.vn xe máy giá | 5 | 0 | 1 / 1 / 0 | 0 | 0 | 0 |

### B - Queries

| Pass | Query | Results | Direct | A/N/R | Blocked | Content | Metadata |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| requirement | tivi giá dưới 10000000 VND xem phim mua giá bán Việt Nam | 5 | 0 | 0 / 2 / 0 | 1 | 0 | 0 |
| requirement | tivi mua chính hãng | 5 | 0 | 1 / 0 / 0 | 1 | 0 | 0 |
| commercial | tivi giá bán sản phẩm | 5 | 0 | 1 / 0 / 0 | 1 | 0 | 0 |
| commercial | tivi mua online | 5 | 0 | 0 / 0 / 0 | 1 | 0 | 0 |
| commercial | site:dienmayxanh.com tivi giá | 5 | 0 | 1 / 0 / 0 | 1 | 0 | 0 |
| merchant_discovery | tivi cửa hàng | 5 | 0 | 0 / 0 / 0 | 2 | 0 | 0 |
| merchant_discovery | tivi đại lý | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:cellphones.com.vn Samsung 55 Inch 4K UA55DU8000KXXV giá | 5 | 4 | 0 / 0 / 0 | 0 | 4 | 0 |
| merchant_products | site:samsung.com Samsung 55 Inch 4K UA55DU8000KXXV giá | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:cellphones.com.vn tivi giá | 5 | 0 | 0 / 1 / 0 | 0 | 0 | 0 |
| merchant_products | site:samsung.com tivi giá | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:dienmaycholon.com tivi giá | 5 | 0 | 1 / 0 / 0 | 0 | 0 | 0 |

### C - Queries

| Pass | Query | Results | Direct | A/N/R | Blocked | Content | Metadata |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| requirement | điện thoại giá dưới 10000000 VND chụp ảnh camera tốt có pin lâu có mua giá bán Việt Nam | 5 | 0 | 1 / 1 / 1 | 1 | 0 | 0 |
| requirement | điện thoại mua chính hãng | 5 | 0 | 0 / 0 / 0 | 1 | 0 | 0 |
| commercial | điện thoại giá bán sản phẩm | 5 | 0 | 0 / 0 / 0 | 1 | 0 | 0 |
| commercial | điện thoại mua online | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| commercial | site:thegioididong.com điện thoại giá | 5 | 0 | 2 / 0 / 0 | 1 | 0 | 0 |
| merchant_discovery | điện thoại cửa hàng | 5 | 0 | 0 / 0 / 0 | 1 | 0 | 0 |
| merchant_discovery | điện thoại đại lý | 5 | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:cellphones.com.vn Samsung Hệ điều hành Android 15 One giá | 5 | 1 | 2 / 2 / 0 | 0 | 1 | 0 |
| merchant_products | site:fptshop.com.vn Samsung Hệ điều hành Android 15 One giá | 5 | 0 | 0 / 5 / 0 | 0 | 0 | 0 |
| merchant_products | site:cellphones.com.vn điện thoại giá | 5 | 0 | 1 / 0 / 0 | 0 | 0 | 0 |
| merchant_products | site:fptshop.com.vn điện thoại giá | 5 | 0 | 0 / 3 / 0 | 0 | 0 | 0 |
| merchant_products | site:daidoangia.vn điện thoại giá | 5 | 1 | 0 / 4 / 0 | 0 | 1 | 0 |


Raw response, candidate data, hard-filter decisions, warning và các lần kiểm tra trước: [LIVE_PRODUCT_CHECK.json](LIVE_PRODUCT_CHECK.json).

## G. Kết luận và thay đổi trong lượt này

**Feature vẫn PARTIAL**: điện thoại đạt tối thiểu một recommendation có trang bán/giá cùng nguồn và ảnh null an toàn; xe máy chưa có verified offer, TV có verified pages nhưng không có sản phẩm trong budget. Chưa đạt cả ba scenario.

Chỉ sửa lỗi kỹ thuật đã thấy: chặn `placehoder.png`, thêm case regression tương ứng; script manual mặc định tôn trọng provider/timeout hiện tại và lưu candidates/filter decisions/giá kiểm tra lại. Không thay query strategy, hard filter, scoring, routes, dependencies, snapshot/history/cache semantics.

Chỉ chạy test liên quan: **55 passed, 0 failed, 1 warning** (`.pytest_cache` thiếu quyền ghi trên Windows). Không chạy lại bộ automated validation đầy đủ mà người dùng đã xác nhận. Không commit/reset/undo Git.
