**Báo cáo tiếp tục `feature/live-universal-product-search` — 2026-09-19**

Giữ các thay đổi hợp lệ có sẵn trong working tree. Không commit/reset/undo; không sửa `.env`, không chạy trên database thật. Kết quả Live và queries đầy đủ nằm trong `LIVE_BUDGET_CHECK.json`; `previous_check` giữ lần chạy trước để không che các lỗi phát hiện khi kiểm tra.

**A. Budget modes**

- `khoảng`/`tầm` + số tiền: `FLEXIBLE_TARGET`.
- `tối đa`/`không quá`/`dưới`: `HARD_MAX`.
- `từ 31 đến 35 triệu` và `31 đến 35 triệu`: `RANGE`.
- Số tiền đứng riêng giữ semantics max của parser cũ. Không diễn giải lại raw query của session lịch sử.
- Python quyết định mode sau extraction. Schema gửi Gemini/OpenAI không chứa mode/target/window do backend tính; tránh lỗi Gemini trả mode mềm nhưng thiếu window.

**B. Tolerance**

6% target, làm tròn đến 10.000đ; khi tolerance đạt 1 triệu thì làm tròn đến 100.000đ. Floor 20.000đ, cap 5 triệu và không lớn hơn chính target.

| Target | Tolerance | Preferred window |
|---|---:|---:|
| 500.000đ | 30.000đ | 470.000–530.000đ |
| 5 triệu | 300.000đ | 4,7–5,3 triệu |
| 10 triệu | 600.000đ | 9,4–10,6 triệu |
| 33 triệu | 2 triệu | 31–35 triệu |
| 100 triệu | 5 triệu | 95–105 triệu |

**C. Hard filter**

HARD_MAX và RANGE vẫn lọc nghiêm, không tolerance. Flexible là ngân sách mềm: preferred window không phải hard exclusion. Giá ngoài window bị giảm điểm và không đủ điều kiện dừng retrieval; có thể còn trong fallback nếu vượt qua category/brand/exclusion/availability. Không có giá vẫn bị loại khi có ngân sách. Điều này giữ Demo laptop 13,99 triệu cho yêu cầu khoảng 15 triệu, không sửa test để bỏ sản phẩm đó.

**D. Price-fit**

Flexible: `clamp(100 - 25 * abs(price-target) / radius, 0, 100)`. Radius lấy từ window đã lưu; target đạt 100, hai biên đạt 75. Không mặc định rẻ nhất tốt nhất. Test xác nhận sản phẩm 34 triệu với evidence yêu cầu tốt hơn xếp trên sản phẩm 31 triệu thiếu evidence. Final weights giữ 25/30/20/10/5/10.

**E. Progressive retrieval**

Các lượt requirement → commercial → model discovery → merchant discovery → merchant products giữ category, budget mode/window, purpose và requirements. Chuẩn hóa tên requirement thành từ tìm kiếm đọc được (ví dụ `fuel_efficiency` → `tiêu thụ nhiên liệu`). Domain lấy từ kết quả web/metadata Product và registry chất lượng sẵn có; không thêm whitelist theo category. Wrapper Tavily hiện nhận query/max-results; giữ `site:` trong query, không tự thêm tham số provider chưa được wrapper hỗ trợ.

Giữ giới hạn config hiện có (cap 180 giây, 24 queries); fetch ưu tiên loại trang, category, commerce, giá/model clue và merchant quality. Ảnh chỉ kiểm tra sau khi page verified và qua hard filter; thiếu ảnh không loại sản phẩm. Không đổi giá/score bằng LLM.

**F. Stop condition**

Đếm product identities có page verified, qua hard filter, nằm trong allowed/preferred budget window. Với requirements: chọn các priority ≥4 (hoặc toàn bộ nếu không có); trọng số có evidence phải >50% tổng và ít nhất một requirement matched. Tái sử dụng comparator của scoring. Unknown giữ làm fallback và tiếp tục trong query/time budget. Khi hết budget, dữ liệu đã tìm được vẫn được chuyển tới pipeline; không xóa kết quả trước đó.

**G. Availability**

Nhận cả `out_of_stock`, `out of stock`, `unavailable`, Schema.org `OutOfStock`/`Discontinued`. Không dùng chúng để dừng thành công; khi chọn offer Live, offer available/unknown đứng trước unavailable. Missing availability không đồng nghĩa hết hàng.

**H. AggregateOffer/model/variant**

Lưu discovery metadata name/brand/model, SKU/color/size khi nguồn có, low/high price khi có VND. AggregateOffer luôn là discovery, kể cả nguồn ghi thêm `price`: không chuyển lowPrice thành offer. Model/variant được đưa vào follow-up query; range được dùng ưu tiên hints gần ngân sách. Manufacturer/model page vẫn phải vượt sales validator trước khi có thể trở thành product_url. `price_type=CONCRETE` và `variant` của recommendation lấy từ proof cùng nguồn; không bịa variant thiếu.

Live phát hiện TV mount bị nhận thành TV vì tên có chữ tivi. Đã sửa nhận diện head noun phụ kiện (giá treo/ốp lưng/bao da/miếng dán) và thêm regression. Không nới sales validator.

**I. UI và tương thích dữ liệu**

Requirement Summary phân biệt “Ngân sách mục tiêu” + “Khoảng giá tham khảo”, “Ngân sách tối đa”, và “Khoảng ngân sách”. Frontend chỉ render backend values. Field budget_min/max cũ vẫn tồn tại; với FLEXIBLE phải dùng budget_target/preferred_min/preferred_max để hiểu semantics mới.

Thêm bảng phụ `requirement_budgets` (1–1 với requirement), JSON metadata; không ALTER cột cũ, không backfill/xóa dữ liệu. `init_db()` tạo bảng còn thiếu khi ứng dụng khởi động. Trong công việc này chỉ khởi động trên database tạm. Requirement cũ không có row giữ min/max cũ; snapshot lưu mode/window cùng recommendation. Cache key phân biệt mode/window, TTL và cơ chế cache/history không đổi; key cũ có thể thành cold miss.

**J. Tests mới/cập nhật**

- `backend/tests/unit/test_budget_retrieval.py`: 47 cases về parser, tolerance, hard/range/soft semantics, score weights, unknown/availability, query/time exhaustion, AggregateOffer discovery, domain hints, phụ kiện, LLM schema.
- `backend/tests/integration/test_budget_semantics_api.py`: 2 tests qua analyze/search/clarify/GET, persistence mới/legacy, snapshot sau session khác cập nhật giá và sau provider fail.
- `backend/tests/unit/test_query_generator.py`: cập nhật assertion exact query thứ hai phải giữ budget/purpose; không bỏ/skip assertion.
- `frontend/tests/budget-summary.test.mjs`: 3 tests render các mode và legacy, xác nhận window lấy nguyên giá trị backend.
- Tất cả automated tests dùng local/mocks, không gọi API trả phí.

**K. Backend regression**

Lần cuối: **393 collected / 393 passed / 0 failed / 2 warnings**, 12,87 giây. Lệnh `.venv\Scripts\python.exe -B -X utf8 -m pytest`, cwd backend. Warnings: Starlette/httpx deprecation hiện có và pytest không ghi được `.pytest_cache` trong sandbox. Database sạch/tạm, không `smart_shopping.db`.

Regression Phase 1–6 vẫn PASS: search fail giữ kết quả/warnings/status; snapshot lịch sử; category; value scoring; weight; analyzer/budget formats; explanation fallback; cache/history; structured evidence/matches.

**L. Frontend regression**

`npm test`: **35 passed, 0 failed**. Có Node `MODULE_TYPELESS_PACKAGE_JSON` warning. `npm run lint`: **PASS, 0 errors / 2 warnings cũ** (compare useMemo và home navigation). `npm run build`: **PASS**. Không nâng dependency hoặc đổi routes.

**M. Browser E2E**

Lần cuối: **4 passed**, 26,5 giây. Demo/local backend + database tạm. Journey home → analysis → search → results → filter/detail/compare/feedback/history; structured match/evidence; snapshot/failure warnings; sales links/image fallback.

**N–Q. Manual Live — kết quả cuối**

Dùng `backend/.env`, DEMO_MODE=false, Tavily thật, SQLite tạm. A/B/C đo trong lần chạy đầy đủ; D kiểm tra lại sau fix category từ URL sản phẩm đã verified. Không dùng Demo products. LLM fallback local chỉ phân tích nhu cầu, không cung cấp dữ liệu sản phẩm.

| Chỉ số | N. Xe máy flexible 33m | O. Xe máy max 33m | P. TV khoảng 10m | Q. Điện thoại khoảng 10m |
|---|---:|---:|---:|---:|
| Queries đã chạy | 12 | 11 | 12 | 12 |
| Tavily results, kể cả trùng URL | 60 | 55 | 60 | 60 |
| URL duy nhất | 44 | 37 | 46 | 40 |
| DIRECT_PRODUCT | 0 | 0 | 2 | 4 |
| ARTICLE / NEWS / REVIEW | 8 / 15 / 0 | 8 / 12 / 0 | 8 / 6 / 2 | 6 / 9 / 1 |
| FETCH_BLOCKED | 9 | 13 | 13 | 4 |
| VERIFIED_CONTENT | 0 | 0 | 2 | 4 |
| VERIFIED_SEARCH_METADATA | 0 | 0 | 0 | 0 |
| Candidates | 0 | 0 | 2 | 4 |
| Bị hard filter loại | 0 | 0 | 0 | 3 |
| Qua hard filter (`total_filtered`) | 0 | 0 | 2 | 1 |
| Recommendations | 0 | 0 | 2 | 1 |

Các loại nguồn/verification trong bảng đếm URL duy nhất; không cộng trùng giữa queries. `total_filtered` của API là số **qua** filter, không phải số bị loại. Tất cả query strings, requirement/category, per-pass counts/rejections và per-source proof nằm trong `LIVE_BUDGET_CHECK.json`.

**N. Xe máy flexible 33m:** mode đúng, target 33m, preferred 31–35m, purpose đi học, tiết kiệm xăng priority 5. Chưa có recommendation. Mất ở page/offer verification trước candidate: 31 URL REJECTED, 13 UNVERIFIED. Nguồn chủ yếu bài viết/tin tức/trang danh mục; metadata fallback thiếu identity title–URL hoặc mang tính editorial. Không lấy giá bài viết/range làm offer. Lượt này không tìm được Product discovery JSON-LD đủ dùng; các hints tên model lấy từ extraction vẫn được đưa vào follow-up.

**O. Xe máy hard max 33m:** mode đúng, không tolerance. 24 URL REJECTED, 13 UNVERIFIED; mất ở verification trước candidate. Không có recommendation vượt 33m (cũng chưa có recommendation nào). Các tests mock riêng đã xác nhận 34m bị loại và 31/33m được chấp nhận.

**P. TV:** target 10m, preferred 9,4–10,6m, purpose xem phim. Hai recommendation verified dưới đây. Mẫu 10,99m ngoài preferred window được giữ vì flexible không hard filter, price-fit thấp hơn và xếp sau mẫu 9,99m.

1. **Smart Tivi 4K Sony KD-50X80J 50 inch Google TV**
   - BRAND: Sony; MODEL: null (model hiển thị trong NAME, nguồn không có field model riêng); VARIANT: SKU `10`.
   - PRICE: **9.990.000 VND**; PRICE_TYPE: CONCRETE; MERCHANT/DOMAIN: mediamart.vn.
   - PRODUCT_URL: https://mediamart.vn/tivi/smart-tivi-4k-sony-kd50x80j-50-inch-android-tv
   - PRODUCT_PAGE_VALID: true; VERIFICATION_LEVEL: VERIFIED_CONTENT; PRODUCT_PAGE_CONFIDENCE: 95.
   - IMAGE_URL: https://cdn.mediamart.vn/images/product/-vm82U4.jpg
   - IMAGE_SOURCE: json_ld_product; IMAGE_LOADS: true.
   - EVIDENCE_URL: cùng PRODUCT_URL. Mở lại nội dung xác nhận đúng tên và giá 9.990.000đ cùng merchant.
   - Price-fit 99,58; final score 70,90. Không có requirement item cụ thể; requirement_matches là empty.

2. **Smart Tivi 4K Sony KD-65X80J 65 inch Google TV**
   - BRAND: Sony; MODEL: null; VARIANT: SKU `23`.
   - PRICE: **10.990.000 VND**; PRICE_TYPE: CONCRETE; MERCHANT/DOMAIN: mediamart.vn.
   - PRODUCT_URL: https://mediamart.vn/tivi/smart-tivi-4k-sony-kd65x80j-65-inch-android-tv
   - PRODUCT_PAGE_VALID: true; VERIFICATION_LEVEL: VERIFIED_CONTENT; PRODUCT_PAGE_CONFIDENCE: 95.
   - IMAGE_URL: https://cdn.mediamart.vn/images/product/-7Slo3D.jpg
   - IMAGE_SOURCE: json_ld_product; IMAGE_LOADS: true.
   - EVIDENCE_URL: cùng PRODUCT_URL. Mở lại nội dung xác nhận đúng tên và giá 10.990.000đ cùng merchant.
   - Price-fit 58,75; final score 60,69. Không có requirement item cụ thể.

**Q. Điện thoại:** target 10m, preferred 9,4–10,6m; clarification `chụp ảnh`. Bốn verified candidates: một được giữ; hai bị loại vì out_of_stock; một vẫn unknown category nên bị loại. Bản trước chưa dùng category rõ ràng trong URL verified của A56 nên loại nhầm candidate đó. Đã sửa fallback category từ title/description/path có evidence, không copy từ requirement. Generic path không có category vẫn unknown (có regression test).

3. **Samsung Galaxy A56 5G 8GB 128GB**
   - BRAND: Samsung; MODEL: null; VARIANT: SKU `dien-thoai-samsung-galaxy-a56`.
   - PRICE: **8.990.000 VND**; PRICE_TYPE: CONCRETE; MERCHANT: CELLPHONES; DOMAIN: cellphones.com.vn.
   - PRODUCT_URL: https://cellphones.com.vn/dien-thoai-samsung-galaxy-a56.html
   - PRODUCT_PAGE_VALID: true; VERIFICATION_LEVEL: VERIFIED_CONTENT; PRODUCT_PAGE_CONFIDENCE: 95.
   - IMAGE_URL: https://cdn2.cellphones.com.vn/insecure/rs:fill:50:50/q:90/plain/https://cellphones.com.vn/media/catalog/product/s/a/samsung-galaxy-a56-hong.jpg
   - IMAGE_SOURCE: html_product_image; IMAGE_LOADS: true; ảnh thumbnail 50×50.
   - EVIDENCE_URL: cùng PRODUCT_URL. Mở lại nội dung xác nhận đúng sản phẩm và giá 8.990.000đ cùng merchant.
   - Battery: **matched**, product value 5000 mAh. Camera tốt: **unknown**, không suy diễn từ megapixel.
   - Price-fit 57,92; requirement score 50; final score 70,28. Đây là fallback ngoài preferred window, không coi là đủ điều kiện stop. Vẫn chạy đủ 12 queries.

**R. Hạn chế và kết luận**

- **Feature Live còn PARTIAL**: TV/phone có direct offers xác minh được; hai tình huống xe máy chưa có recommendation. Không nới validator, không bịa price/URL/model/ảnh để tạo kết quả.
- Gemini có 503 UNAVAILABLE và 429 RESOURCE_EXHAUSTED (quota free tier). Phân tích điện thoại fallback local; dữ liệu sản phẩm vẫn từ Tavily/merchant Live. Trong các lượt cuối báo cáo không có Tavily query error/timeout; FETCH_BLOCKED là lỗi fetch trang nguồn, không phải Tavily quota.
- Domain discovery vẫn có thể chọn nhầm domain tin tức chưa được phân loại khi HTML bị chặn. Long intent queries có thể chủ yếu trả bài tổng hợp. Đây là giới hạn recall còn lại, không bằng chứng cho phép chấp nhận các trang đó thành offer.
- Metadata discovery chỉ giữ dữ liệu nguồn thực sự có. JSON-LD thiếu model thì API để null; không backfill từ tên bằng phỏng đoán. Variant mới hỗ trợ dữ liệu tường minh SKU/color/size và tên variant từ nguồn, chưa xác minh được mọi selector JS.
- Ba ảnh đã tải/mở được. Hai URL ảnh TV có cùng nội dung (ảnh mặt sau), dù mỗi trang Product JSON-LD gán cho một kích thước riêng; provenance đã xác nhận nhưng không có xác minh độc lập kích thước/model từ pixels. Ảnh A56 đúng tên model trong URL/alt, kích thước thumbnail nhỏ. Khả năng chứng nhận ảnh chính xác từng variant vẫn có giới hạn.
- Flexible window là tham khảo, nên fallback có thể ngoài window. UI và điểm thể hiện mode/price-fit; không tuyên bố fallback đó nằm trong khoảng tham khảo.
- Không sửa ngoài công việc retrieval/budget/variant và những lỗi kỹ thuật trực tiếp phát hiện trong manual verification. Không đổi routes, scoring weights, stack/dependencies, cache TTL/history semantics; không sửa database thật; không commit Git.

**Files sửa/tạo trong lần tiếp tục này**

Backend: `app/services/budget.py` (mới), `app/models/requirement.py`, `app/schemas/requirement.py`, `app/schemas/product.py`, `app/schemas/recommendation.py`, `app/api/routes/requirements.py`, `app/api/routes/products.py`, `app/services/llm/client.py`, `app/services/llm/requirement_analyzer.py`, `app/services/llm/query_generator.py`, `app/services/filter/hard_filter.py`, `app/services/scoring/scoring_engine.py`, `app/services/cache/search_cache.py`, `app/services/recommendation/candidate_builder.py`, `app/services/recommendation/recommendation_service.py`, `app/services/search/progressive_retrieval.py`, `app/services/search/merchant_quality.py`, `app/services/extraction/product_discovery.py` (mới), `app/services/extraction/product_page_validator.py`, `app/services/extraction/search_metadata_validator.py`, `app/services/normalization/product_normalizer.py`, `scripts/check_live_sales.py` và ba test files nêu trên.

Frontend: `types/shopping.ts`, `components/requirement-summary.tsx`, `tests/budget-summary.test.mjs` (mới). Docs: báo cáo này và `LIVE_BUDGET_CHECK.json` (mới). Các thay đổi feature có sẵn khác trong Git được giữ nguyên.
