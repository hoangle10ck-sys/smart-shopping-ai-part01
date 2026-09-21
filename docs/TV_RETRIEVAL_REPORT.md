# Live universal search — TV continuation và regression cuối

Tiếp tục working tree trên `feature/live-universal-product-search`; không reset, undo hoặc commit. Báo cáo electronics/motorcycle trước được giữ nguyên. Dữ liệu của lần chạy mới nằm tại [LIVE_TV_CHECK.json](LIVE_TV_CHECK.json).

## A. Hai test cũ và request context

`test_unknown_evidence_keeps_fallback_and_searches_to_query_budget` vẫn kiểm tra đủ query budget, fallback hợp lệ, chưa đủ evidence để dừng và không yêu cầu ảnh. Query của pass `requirement` phải giữ purpose, requirement, target/window. Query generic chỉ cần category/target; query exact được phép ngắn.

`test_aggregate_feeds_model_variant_followups_with_budget_and_intent` vẫn bắt buộc discovery dẫn đến lookup đúng model/variant, bao gồm exact query `"Honda Example X1 Đỏ" mua`. Aggregate không được trở thành concrete offer.

Cả hai test bổ sung so sánh **toàn bộ** `requirement_context == req.model_dump()` ở từng diagnostic. Category, budget mode, target/window, purpose và requirements không bị mất khi rút ngắn query string. Không bỏ assertion về giá, eligibility, variant hoặc điều kiện dừng.

## B. TV accessory handling

Root cause: category alias `TV` có thể match tên phụ kiện `Android TV Box` hoặc `HDMI cable for TV`. Bổ sung nhận diện danh từ sản phẩm ở đầu tên: TV box/Android TV box/box TV, HDMI cable/cáp HDMI. Tái sử dụng guard phụ kiện hiện có trước khi xét source category. Không copy category từ requirement.

Regression bao gồm TV box, Android TV box, HDMI cable, cáp HDMI, remote, giá treo, chân đế, kệ, phụ kiện và AirTag. Bốn ca positive giữ Smart TV, Tivi Sony, Samsung TV, LG TV là `tivi`; fixture có identity/brand/model và Offer rõ ràng. Normalization riêng vẫn nhận `Smart TV X200`; sales-page identity validator không bị nới để chấp nhận một title quá ít identity tokens.

## C. Hết hàng và availability unknown

Hard filter hiện có đã loại OutOfStock đúng; lỗi nằm ở các query tiếp theo có thể tiếp tục bám cùng model/merchant. `model_progress` ghi attempts, state, failed domains và exhausted vào diagnostics. Hết hàng không tạo primary recommendation và không làm retrieval đủ điều kiện dừng. Sau mỗi query tiếp tục, đánh giá lại trước khi chọn query mới.

Không công bố availability vẫn eligible nếu các điều kiện khác hợp lệ; không suy ra hết hàng. Requirement chưa đủ evidence vẫn UNKNOWN, có thể giữ fallback nhưng không tự coi satisfied. Không sửa hard-filter/budget/scoring logic trong lượt này.

## D. Alternative model/merchant strategy

Thay một commercial query quá dài bằng generic category + target query; vẫn giữ requirement-aware queries. Giảm merchant discovery xuống một query để dành slots cho follow-up. Continuation luân phiên exact model chưa thử và merchant lookup; merchant đã thử nhiều/hết hàng được xếp sau. Giới hạn hai scoped queries/domain và không lặp model đã dùng hết lượt. Sau lượt scoped đầu, các merchant khác được tìm bằng category/budget để tránh cùng SKU chiếm mọi slot.

Chỉ dùng model được quan sát từ nguồn và merchant discovery/SourceStrategy hiện có. Không thêm danh sách model, URL hoặc seller riêng để ép scenario PASS. Không thay validator, parser giá/variant/màu, category helper điện thoại/xe máy, image policy, schema, routes hoặc trọng số.

### File sửa/tạo trong lượt tiếp tục này

- `backend/app/services/search/progressive_retrieval.py`: query diversification, continuation và model progress diagnostics.
- `backend/app/services/normalization/product_normalizer.py`: nhận diện TV box/cáp HDMI.
- `backend/app/services/search/retrieval_diagnostics.py`: bổ sung CATEGORY, MERCHANT, AVAILABILITY vào source audit.
- `backend/scripts/check_live_sales.py`: ghi lần Live mới riêng tại `docs/LIVE_TV_CHECK.json`.
- `backend/tests/unit/test_budget_retrieval.py`: semantics và assertions context của hai test cũ.
- `backend/tests/unit/test_tv_retrieval.py`: 22 regression cases, mới.
- `docs/TV_RETRIEVAL_REPORT.md`, `docs/LIVE_TV_CHECK.json`: báo cáo lần này.

Working tree còn có thay đổi hợp lệ từ các lượt trước; danh sách trên không phải toàn bộ diff so với HEAD.

## E. Backend final tests

Focused: `pytest tests/unit/test_tv_retrieval.py tests/unit/test_model_hints.py tests/unit/test_progressive_retrieval.py tests/unit/test_budget_retrieval.py tests/integration/test_electronics_retrieval.py`: **121 collected / 121 PASS / 0 FAIL / 2 warnings**, 4,05 giây.

Sau focused PASS, chạy `.venv\Scripts\python.exe -B -X utf8 -m pytest`: **522 collected / 522 PASS / 0 FAIL / 2 warnings**, 20,24 giây. Số mới sau source cuối, không dùng lại 500/518. Warnings: Starlette/httpx deprecation và pytest không ghi được cache do quyền filesystem. Schema được tự tạo trong SQLite tạm; không dùng `smart_shopping.db`.

Toàn bộ regression trước vẫn PASS, bao gồm session failure/snapshot, category, requirement value, weight/budget/analyzer, evidence, cache/history, 45 dealer parser tests, phone/TV integration và variant/category helper tests.

## F. Frontend final tests

`npm test`: **35 collected / 35 PASS / 0 FAIL**, không skip. Có Node `MODULE_TYPELESS_PACKAGE_JSON` warning cũ. Không sửa frontend trong lượt này.

## G. Lint/build

`npm run lint`: **PASS, 0 errors / 2 warnings cũ**: compare page useMemo dependency (line 149) và home page navigation (line 397). `npm run build`: **PASS**, compile, TypeScript và static generation thành công.

## H. Browser E2E

`npm run test:e2e`: **4/4 PASS**, 24,9 giây. Demo/local backend với SQLite tạm; không gọi API trả phí. Scenarios: shopping journey từ home đến history; structured match/evidence; historical snapshot/failure warnings; verified sales links và broken-image placeholder. Cảnh báo NO_COLOR/FORCE_COLOR của runner không phải test failures.

## I. Motorcycle flexible Live — PASS

Target 33 triệu, cửa sổ mềm 31–35 triệu, purpose đi học, requirement tiết kiệm xăng. 12 queries/60 Tavily results; 8 candidates, 1 bị hard filter loại, 7 còn lại, 5 recommendations. Ba phiên bản Vision trong cửa sổ mềm: cao cấp 32.979.273, đặc biệt 34.353.818, tiêu chuẩn 31.310.182 đồng. Vision thể thao 36.612.000 và Winner X tiêu chuẩn 46.160.000 đồng là fallback ngoài cửa sổ, điểm budget thấp hơn; không gọi chúng là khớp ngân sách mục tiêu. Evidence tiết kiệm xăng vẫn UNKNOWN. Tất cả đều InStock, concrete same-variant price tại HEAD T&H và đã mở lại xác nhận.

## J. Motorcycle hard-max Live — PASS

Hard maximum 33 triệu, purpose đi học. 6 queries/30 results; 4 candidates, 2 bị loại vì budget, 2 recommendations: Vision cao cấp 32.979.273 và tiêu chuẩn 31.310.182 đồng tại HEAD T&H. Không recommendation nào vượt 33 triệu. Cả hai mở lại đúng giá và InStock.

## K. TV Live — PASS

Tám queries, gồm requirement-aware, generic category/target, exact Samsung U8500F, alternative LG UA7350 và merchant CellphoneS. Exact global queries chủ yếu dẫn tới trang hãng nước ngoài, không tạo offer nếu thiếu concrete seller price. Query `site:cellphones.com.vn "Samsung U8500F" giá bán` tìm được ba direct product pages; hai offer được giữ, một offer hết hàng bị loại.

- **55U8500F, 9.790.000 đồng, CellphoneS, InStock**: nằm trong cửa sổ mềm 9,4–10,6 triệu, đủ điều kiện TV acceptance. Category từ breadcrumb Tivi; identity đầy đủ trong Product name/H1/SKU. `model` field riêng vẫn null vì nguồn không khai báo field đó, không tự điền.
- **65U8500F, 11.690.000 đồng, CellphoneS, InStock**: fallback ngoài cửa sổ mềm; budget score 29,58, thấp hơn 91,25 của 55U8500F. Không biến target thành hard maximum.
- **50U8500F, 8.390.000 đồng, CellphoneS, OutOfStock**: verified identity/price/category nhưng bị loại ở `availability`, reason `Sản phẩm hiện không còn hàng.`, `STOP_READY=false`. Không tính vào recommendations hoặc acceptance.

Cả hai recommendation đã GET lại direct page, giá mới kiểm tra bằng đúng giá recommendation, confidence 95/VERIFIED_CONTENT; không homepage/category/search/article. Ảnh đều null, không cản recommendation. Purpose `xem phim` chưa có evidence để chấm: purpose score 0; requirements rỗng không mang nghĩa đã chứng minh chất lượng xem phim.

Live lần này tìm được hàng hợp lệ trong cùng batch có offer hết hàng. Hành vi tiếp tục **sau một batch chỉ có hàng hết** được kiểm tra riêng bằng regression mocked; không gọi đó là trình tự đã xảy ra trong Live này.

## L. Phone Live — PASS theo điều kiện direct valid offer

Clarification `chụp ảnh`; category điện thoại, target 10 triệu, cửa sổ mềm 9,4–10,6 triệu; requirements camera tốt/pin lâu. 12 queries/60 results; 5 candidates, 2 hết hàng bị loại, 3 recommendations InStock với cùng offer/price được mở lại xác nhận:

- Xiaomi Redmi Note 17 Pro Max 5G 8GB/512GB, CellphoneS, **14.490.000 đồng**.
- Xiaomi Redmi Note 17 Pro 5G 6GB/256GB, Hoàng Hà Mobile, **8.990.000 đồng**.
- Vivo V30 5G 12GB/512GB **Like New**, Đức Huy Mobile, **6.399.000 đồng**.

Cả ba ngoài cửa sổ mềm, chỉ là fallback hợp lệ; không tuyên bố đã có điện thoại trong khoảng giá ưu tiên. Camera vẫn UNKNOWN cả ba. Pin của Note 17 Pro Max có source value 10.000 mAh và matched theo rule Python hiện có; pin hai máy còn lại UNKNOWN. Không sửa trọng số hoặc luật scoring để ép thứ hạng. Ba ảnh tải được, có provenance từ Product JSON-LD của chính trang bán; đã mở ảnh để kiểm tra, không dùng search image.

## M. Secret scan

Quét **21 files** `docs/*.md` và `docs/*.json` theo `api[_-]?key`, `authorization`, `bearer`, `secret`, `token`; đồng thời so sánh các credential thực tế từ cấu hình trong bộ nhớ và kiểm tra credential patterns. Không in giá trị cấu hình. Keyword hits là nội dung tài liệu, tên biến hoặc ví dụ rỗng; **0 credential hits**. `backend/.env` không tracked và hash không đổi.

## N. Git diff/check

`git diff --check`: PASS. Toàn working tree kế thừa: **38 tracked files modified, 40 untracked, 0 staged**; diff tracked **+595/-500**. Untracked bao gồm source/tests/báo cáo từ các lượt trước và lượt này; không nằm trong diff stat mặc định của Git. Không staging/commit/reset/undo. Các file parser dealer, category evidence helper, budget, scoring và backend/.env có SHA-256 giữ nguyên so với đầu lượt.

## O. Kết luận

**PASS theo acceptance bốn scenario Live của yêu cầu này**, cùng toàn bộ regression mới. Không tương đương hoàn tất mọi mục MASTER_SPEC hoặc bảo đảm luôn có hàng/giá phù hợp ở mọi thời điểm.

Giới hạn còn lại: phone chưa có offer trong cửa sổ mềm; một số fallback xe máy/TV/phone xa target; evidence purpose/camera/tiết kiệm xăng chưa đủ; TV model field riêng null dù name/SKU xác định model; TV không có ảnh được xác minh. Hai lint warnings cũ giữ nguyên. Không xử lý các vấn đề này ngoài phạm vi.

Provider: Tavily không có query errors/timeouts/quota trong lần cuối. Có các trang nguồn FETCH_BLOCKED hoặc không đủ metadata, được giữ unverified và không nâng thành offer. Gemini báo 429 RESOURCE_EXHAUSTED (daily free-tier quota 20) ở analysis/clarification; fallback hiện có được dùng. Một số explanation scenario A dùng Gemini, các explanation còn lại dùng fallback. Không dùng Demo products; DB Live là SQLite tạm và được đóng/xóa sau chạy.

## Detailed Live observations

Run started (UTC): 2026-09-21T00:41:33.786825+00:00. All four scenarios are from this run; no previous run is merged.

Counts are source occurrences summed per query, not unique URLs. DIRECT_PRODUCT counts pages, while candidates count concrete offers/variants. Hard-filtered means rejected; total_filtered means remaining.

| Scenario | Queries | Tavily | DIRECT_PRODUCT | ARTICLE/NEWS/REVIEW | FETCH_BLOCKED | VERIFIED_CONTENT | VERIFIED_SEARCH_METADATA | Candidates | Hard-filtered | Remaining | Recommendations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 12 | 60 | 4 | 29 | 12 | 4 | 0 | 8 | 1 | 7 | 5 |
| B | 6 | 30 | 1 | 14 | 5 | 1 | 0 | 4 | 2 | 2 | 2 |
| C | 8 | 40 | 3 | 9 | 15 | 3 | 0 | 3 | 1 | 2 | 2 |
| D | 12 | 60 | 5 | 25 | 12 | 5 | 0 | 5 | 2 | 3 | 3 |

### Scenario A: Tôi cần xe máy khoảng 33 triệu để đi học, ưu tiên tiết kiệm xăng.

Requirement as returned by backend:

```json
{
  "budget_mode": "FLEXIBLE_TARGET",
  "budget_target": 33000000,
  "preferred_min": 31000000,
  "preferred_max": 35000000,
  "category": "xe máy",
  "budget_min": null,
  "budget_max": 33000000,
  "currency": "VND",
  "purpose": [
    "đi học"
  ],
  "brands": [],
  "requirements": [
    {
      "name": "tiết kiệm xăng",
      "value": "tiết kiệm xăng",
      "priority": 5
    }
  ],
  "excluded_requirements": [],
  "sort_preference": "best_match",
  "confidence": 0.95
}
```

Queries executed (in diagnostic order):

- `requirement`: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiết kiệm xăng tiết kiệm xăng mua giá bán Việt Nam (5 results)
- `requirement`: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiết kiệm xăng tiết kiệm xăng mua chính hãng (5 results)
- `commercial`: xe máy giá khoảng 33000000 VND giá bán (5 results)
- `commercial`: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiết kiệm xăng tiết kiệm xăng mua online (5 results)
- `model_discovery`: "Yamaha Gear 125 Hybrid" mua (5 results)
- `model_discovery`: "Honda Vision" mua (5 results)
- `merchant_discovery`: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiết kiệm xăng tiết kiệm xăng đại lý (5 results)
- `merchant_products`: site:hondath.vn "Yamaha Gear 125 Hybrid" giá bán (5 results)
- `merchant_products`: "Honda SH 350i" giá (5 results)
- `merchant_products`: site:xemayhungthanhdat.com xe máy giá khoảng 33000000 VND giá bán (5 results)
- `merchant_products`: "Honda Vision Promos" giá (5 results)
- `merchant_products`: site:honda.com.vn xe máy giá khoảng 33000000 VND giá bán (5 results)

#### A1. Honda Vision - cao cap

```text
NAME: "Honda Vision - cao cap"
BRAND: "Honda"
MODEL: "Vision"
VARIANT: {"attribute_pa_phien-ban": "cao-cap", "color_options": "do-xam"}
PRICE_TYPE: "CONCRETE"
PRICE: 32979273
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2026/05/vision-cao-cap-mau-do-xam.png"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 32979273
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 99.74,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 29.94
  },
  "requirement_matches": [
    {
      "name": "tiết kiệm xăng",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

#### A2. Honda Vision - dac biet

```text
NAME: "Honda Vision - dac biet"
BRAND: "Honda"
MODEL: "Vision"
VARIANT: {"attribute_pa_phien-ban": "dac-biet", "color_options": "nau-xam"}
PRICE_TYPE: "CONCRETE"
PRICE: 34353818
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2026/05/vision-dac-biet-mau-nau-xam.png"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 34353818
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
EXPLANATION_MODE: "gemini"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 83.08,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 25.77
  },
  "requirement_matches": [
    {
      "name": "tiết kiệm xăng",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

#### A3. Honda Vision - tieu chuan

```text
NAME: "Honda Vision - tieu chuan"
BRAND: "Honda"
MODEL: "Vision"
VARIANT: {"attribute_pa_phien-ban": "tieu-chuan", "color_options": "trang-den"}
PRICE_TYPE: "CONCRETE"
PRICE: 31310182
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2026/05/vision-tieu-chuan-mau-trang.png"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 31310182
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
EXPLANATION_MODE: "gemini"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 78.88,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 24.72
  },
  "requirement_matches": [
    {
      "name": "tiết kiệm xăng",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

#### A4. Honda Vision - the thao

```text
NAME: "Honda Vision - the thao"
BRAND: "Honda"
MODEL: "Vision"
VARIANT: {"attribute_pa_phien-ban": "the-thao", "color_options": "bac-den / den / xam-den"}
PRICE_TYPE: "CONCRETE"
PRICE: 36612000
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2026/05/vision-the-thao-mau-xam-den.png"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 36612000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 54.85,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 18.71
  },
  "requirement_matches": [
    {
      "name": "tiết kiệm xăng",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

#### A5. Honda Winner X - tieu chuan

```text
NAME: "Honda Winner X - tieu chuan"
BRAND: "Honda"
MODEL: "Winner X"
VARIANT: {"attribute_pa_phien-ban": "tieu-chuan", "color_options": "den-bac / do-den / trang-den"}
PRICE_TYPE: "CONCRETE"
PRICE: 46160000
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-con-tay/honda-winner-x"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2024/06/Honda-Xe-con-tay-Winner-X-2024-ban-tieu-chuan-mau-den-bac-1.jpg"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-con-tay/honda-winner-x"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 46160000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-con-tay/honda-winner-x"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 0.0,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 5.0
  },
  "requirement_matches": [
    {
      "name": "tiết kiệm xăng",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

### Scenario B: Tôi cần xe máy tối đa 33 triệu để đi học.

Requirement as returned by backend:

```json
{
  "budget_mode": "HARD_MAX",
  "budget_target": null,
  "preferred_min": null,
  "preferred_max": null,
  "category": "xe máy",
  "budget_min": null,
  "budget_max": 33000000,
  "currency": "VND",
  "purpose": [
    "đi học"
  ],
  "brands": [],
  "requirements": [],
  "excluded_requirements": [],
  "sort_preference": "best_match",
  "confidence": 0.85
}
```

Queries executed (in diagnostic order):

- `requirement`: xe máy giá dưới 33000000 VND đi học mua giá bán Việt Nam (5 results)
- `requirement`: xe máy giá dưới 33000000 VND đi học mua chính hãng (5 results)
- `commercial`: xe máy giá dưới 33000000 VND giá bán (5 results)
- `commercial`: xe máy giá dưới 33000000 VND đi học mua online (5 results)
- `model_discovery`: "Honda Vision" mua (5 results)
- `model_discovery`: "Yamaha Janus" mua (5 results)

#### B1. Honda Vision - cao cap

```text
NAME: "Honda Vision - cao cap"
BRAND: "Honda"
MODEL: "Vision"
VARIANT: {"attribute_pa_phien-ban": "cao-cap", "color_options": "do-xam"}
PRICE_TYPE: "CONCRETE"
PRICE: 32979273
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2026/05/vision-cao-cap-mau-do-xam.png"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 32979273
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 99.98,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 60.0
  },
  "requirement_matches": []
}
```

#### B2. Honda Vision - tieu chuan

```text
NAME: "Honda Vision - tieu chuan"
BRAND: "Honda"
MODEL: "Vision"
VARIANT: {"attribute_pa_phien-ban": "tieu-chuan", "color_options": "trang-den"}
PRICE_TYPE: "CONCRETE"
PRICE: 31310182
MERCHANT: "HEAD T&amp;H"
DOMAIN: "hondath.vn"
CATEGORY: "xe máy"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://hondath.vn/wp-content/uploads/2026/05/vision-tieu-chuan-mau-trang.png"
IMAGE_SOURCE: "product_variation_image"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 31310182
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hondath.vn/xe-may/xe-ga/honda-vision"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 98.46,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 59.62
  },
  "requirement_matches": []
}
```

### Scenario C: Tôi cần TV khoảng 10 triệu để xem phim.

Requirement as returned by backend:

```json
{
  "budget_mode": "FLEXIBLE_TARGET",
  "budget_target": 10000000,
  "preferred_min": 9400000,
  "preferred_max": 10600000,
  "category": "tivi",
  "budget_min": null,
  "budget_max": 10000000,
  "currency": "VND",
  "purpose": [
    "xem phim"
  ],
  "brands": [],
  "requirements": [],
  "excluded_requirements": [],
  "sort_preference": "best_match",
  "confidence": 0.85
}
```

Queries executed (in diagnostic order):

- `requirement`: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua giá bán Việt Nam (5 results)
- `requirement`: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua chính hãng (5 results)
- `commercial`: tivi giá khoảng 10000000 VND giá bán (5 results)
- `commercial`: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua online (5 results)
- `model_discovery`: "Samsung U8500F" mua (5 results)
- `model_discovery`: "LG UA7350" mua (5 results)
- `merchant_discovery`: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim đại lý (5 results)
- `merchant_products`: site:cellphones.com.vn "Samsung U8500F" giá bán (5 results)

#### C1. Smart Tivi Samsung UHD 4K 55 inch 2025 (55U8500F)

```text
NAME: "Smart Tivi Samsung UHD 4K 55 inch 2025 (55U8500F)"
BRAND: "Samsung"
MODEL: null
VARIANT: {"sku": "TV-SS-55U8500F-UHD-4K-55"}
PRICE_TYPE: "CONCRETE"
PRICE: 9790000
MERCHANT: "CELLPHONES"
DOMAIN: "cellphones.com.vn"
CATEGORY: "tivi"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://cellphones.com.vn/smart-tivi-samsung-uhd-55u8500f-4k-55-inch-2025.html"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: null
IMAGE_SOURCE: null
IMAGE_LOADS: false
EVIDENCE_URL: "https://cellphones.com.vn/smart-tivi-samsung-uhd-55u8500f-4k-55-inch-2025.html"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 9790000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://cellphones.com.vn/smart-tivi-samsung-uhd-55u8500f-4k-55-inch-2025.html"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 91.25,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 90.0,
    "final_score": 61.81
  },
  "requirement_matches": []
}
```

#### C2. Smart Tivi Samsung UHD 4K 65 inch 2025 (65U8500F)

```text
NAME: "Smart Tivi Samsung UHD 4K 65 inch 2025 (65U8500F)"
BRAND: "Samsung"
MODEL: null
VARIANT: {"sku": "TV-SS-65U8500F-UHD-4K-65"}
PRICE_TYPE: "CONCRETE"
PRICE: 11690000
MERCHANT: "CELLPHONES"
DOMAIN: "cellphones.com.vn"
CATEGORY: "tivi"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://cellphones.com.vn/smart-tivi-samsung-uhd-65u8500f-4k-65-inch-2025.html"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: null
IMAGE_SOURCE: null
IMAGE_LOADS: false
EVIDENCE_URL: "https://cellphones.com.vn/smart-tivi-samsung-uhd-65u8500f-4k-65-inch-2025.html"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 11690000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://cellphones.com.vn/smart-tivi-samsung-uhd-65u8500f-4k-65-inch-2025.html"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 29.58,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 90.0,
    "final_score": 46.4
  },
  "requirement_matches": []
}
```

### Scenario D: Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu.

Requirement as returned by backend:

```json
{
  "budget_mode": "FLEXIBLE_TARGET",
  "budget_target": 10000000,
  "preferred_min": 9400000,
  "preferred_max": 10600000,
  "category": "điện thoại",
  "budget_min": null,
  "budget_max": 10000000,
  "currency": "VND",
  "purpose": [
    "chụp ảnh"
  ],
  "brands": [],
  "requirements": [
    {
      "name": "battery",
      "value": "pin lâu",
      "priority": 4
    },
    {
      "name": "camera",
      "value": "tốt",
      "priority": 4
    }
  ],
  "excluded_requirements": [],
  "sort_preference": "best_match",
  "confidence": 0.95
}
```

Queries executed (in diagnostic order):

- `requirement`: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua giá bán Việt Nam (5 results)
- `requirement`: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua chính hãng (5 results)
- `commercial`: điện thoại giá khoảng 10000000 VND giá bán (5 results)
- `commercial`: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua online (5 results)
- `model_discovery`: "Vivo V30E 12GB 256GB" mua (5 results)
- `model_discovery`: "Samsung Galaxy A56 5G" mua (5 results)
- `merchant_discovery`: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt đại lý (5 results)
- `merchant_products`: site:us.smartprix.com "Vivo V30e" giá bán (5 results)
- `merchant_products`: "Vivo V30 5G" giá (5 results)
- `merchant_products`: site:thegioididong.com điện thoại giá khoảng 10000000 VND giá bán (5 results)
- `merchant_products`: "Redmi Note 17 Pro 5G 8GB/256GB" giá (5 results)
- `merchant_products`: site:duchuymobile.com điện thoại giá khoảng 10000000 VND giá bán (5 results)

#### D1. Xiaomi Redmi Note 17 Pro Max 5G 8GB 512GB

```text
NAME: "Xiaomi Redmi Note 17 Pro Max 5G 8GB 512GB"
BRAND: "Xiaomi"
MODEL: null
VARIANT: {"sku": "dien-thoai-xiaomi-redmi-note-17-pro-max-5g"}
PRICE_TYPE: "CONCRETE"
PRICE: 14490000
MERCHANT: "CELLPHONES"
DOMAIN: "cellphones.com.vn"
CATEGORY: "điện thoại"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://cellphones.com.vn/dien-thoai-xiaomi-redmi-note-17-pro-max-5g.html"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://cdn2.cellphones.com.vn/200x/media/catalog/product/x/i/xiaomi-redmi-note-17-pro-max-5g-white.jpg"
IMAGE_SOURCE: "json_ld_product"
IMAGE_LOADS: true
EVIDENCE_URL: "https://cellphones.com.vn/dien-thoai-xiaomi-redmi-note-17-pro-max-5g.html"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 14490000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://cellphones.com.vn/dien-thoai-xiaomi-redmi-note-17-pro-max-5g.html"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 0.0,
    "requirement_score": 50.0,
    "purpose_score": 100.0,
    "rating_score": 100.0,
    "review_score": 20.0,
    "source_score": 90.0,
    "final_score": 55.0
  },
  "requirement_matches": [
    {
      "name": "battery",
      "requested_value": "pin lâu",
      "product_value": "10000 mAh",
      "status": "matched",
      "reason": "Giá trị đáp ứng quy tắc so sánh deterministic."
    },
    {
      "name": "camera",
      "requested_value": "tốt",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

#### D2. Xiaomi Redmi Note 17 Pro 5G 6GB/256GB

```text
NAME: "Xiaomi Redmi Note 17 Pro 5G 6GB/256GB"
BRAND: "Xiaomi"
MODEL: "Redmi Note 17 Pro 5G 6GB/256GB"
VARIANT: {"sku": "2607DRA18GDN"}
PRICE_TYPE: "CONCRETE"
PRICE: 8990000
MERCHANT: "Hoàng Hà Mobile"
DOMAIN: "hoanghamobile.com"
CATEGORY: "điện thoại"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://hoanghamobile.com/dien-thoai/xiaomi-redmi-note-17-pro-5g"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://cdn.hoanghamobile.vn/i/preview/Uploads/2026/08/17/q16-purple-back11-160338679.png"
IMAGE_SOURCE: "json_ld_product"
IMAGE_LOADS: true
EVIDENCE_URL: "https://hoanghamobile.com/dien-thoai/xiaomi-redmi-note-17-pro-5g"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 8990000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://hoanghamobile.com/dien-thoai/xiaomi-redmi-note-17-pro-5g"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 57.92,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 19.48
  },
  "requirement_matches": [
    {
      "name": "battery",
      "requested_value": "pin lâu",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    },
    {
      "name": "camera",
      "requested_value": "tốt",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

#### D3. Vivo V30 5G (12GB | 512GB) Chính Hãng Like New

```text
NAME: "Vivo V30 5G (12GB | 512GB) Chính Hãng Like New"
BRAND: "Vivo"
MODEL: "V30 5G 12GB 512GB Chính Hãng"
VARIANT: {}
PRICE_TYPE: "CONCRETE"
PRICE: 6399000
MERCHANT: "Đức Huy Mobile"
DOMAIN: "www.duchuymobile.com"
CATEGORY: "điện thoại"
AVAILABILITY: "in_stock"
PRODUCT_URL: "https://www.duchuymobile.com/vivo-v30-5g"
PRODUCT_PAGE_VALID: true
VERIFICATION_LEVEL: "VERIFIED_CONTENT"
PRODUCT_PAGE_CONFIDENCE: 95.0
IMAGE_URL: "https://www.duchuymobile.com/images/variant_image/69/vivo-v30-5g-den.jpg"
IMAGE_SOURCE: "json_ld_product"
IMAGE_LOADS: true
EVIDENCE_URL: "https://www.duchuymobile.com/vivo-v30-5g"
MANUAL_CONTENT_CONFIRMED: true
MANUAL_PRICE: 6399000
MANUAL_PRICE_MATCHES: true
MANUAL_FINAL_URL: "https://www.duchuymobile.com/vivo-v30-5g"
EXPLANATION_MODE: "fallback"
```

Score and observed requirement matches:

```json
{
  "score": {
    "budget_score": 0.0,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 100.0,
    "review_score": 20.0,
    "source_score": 50.0,
    "final_score": 16.0
  },
  "requirement_matches": [
    {
      "name": "battery",
      "requested_value": "pin lâu",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    },
    {
      "name": "camera",
      "requested_value": "tốt",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ]
}
```

### TV source audit index

Every query-source observation, including full QUERY, TITLE, SNIPPET, BRAND, MODEL, DOMAIN, MERCHANT, URL, CATEGORY, CATEGORY_EVIDENCE, PRICE, AVAILABILITY, VERIFICATION_LEVEL, REJECT_STAGE and REJECT_REASON, is preserved in `scenarios[2].source_audit` in [LIVE_TV_CHECK.json](LIVE_TV_CHECK.json). Null means unavailable evidence. The index below lists each unique URL once; the JSON retains repeated query observations.

| URL | Stage | Reason |
|---|---|---|
| https://meta.vn/hotro/top-tivi-55-inch-duoi-10-trieu-tot-nhat-17485 | source_type | Trang không phải trang bán sản phẩm: ARTICLE |
| https://www.youtube.com/watch?v=zxpdxr2Wnn8 | source_type | Editorial/multiple-product search metadata. |
| https://www.youtube.com/watch?v=vKVatWhJhTM | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://cellphones.com.vn/tivi.html | source_type | Trang không phải trang bán sản phẩm: CATEGORY |
| https://dienmaythienphu.vn/tin-tuc/tu-van-tivi/tam-gia-10-15-trieu-nen-mua-tivi-nao-vua-dep-vua-chat-luong | source_type | URL là trang chủ/danh mục/tìm kiếm/bài viết hoặc không an toàn. |
| https://www.tnc.com.vn/top-10-tivi-ban-chay-hien-nay.html | source_type | Trang không phải trang bán sản phẩm: NEWS |
| https://www.youtube.com/watch?v=L2TzecHYfJU | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://www.youtube.com/watch?v=NKYzqW8oPQ4 | source_type | Editorial/multiple-product search metadata. |
| https://meta.vn/tivi-c3256 | source_type | Trang không phải trang bán sản phẩm: CATEGORY |
| https://dienmaythienphu.vn/tin-tuc/3-mau-tivi-gia-re-co-gia-9-trieu-vnd-dang-mua-cho-gia-dinh-minh | source_type | URL là trang chủ/danh mục/tìm kiếm/bài viết hoặc không an toàn. |
| https://www.youtube.com/watch?v=O8xK_Gzp9R8 | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://dienmaythienphu.vn/tin-tuc/tu-van-tivi/nen-mua-tivi-nao-trong-tam-gia-10-trieu-dong-chia-se-3-mau-tivi-cua-samsung-sony-va-lg | source_type | URL là trang chủ/danh mục/tìm kiếm/bài viết hoặc không an toàn. |
| https://manhnguyen.com.vn/tivi | source_type | URL là trang chủ/danh mục/tìm kiếm/bài viết hoặc không an toàn. |
| https://www.samsung.com/my/tvs/uhd-4k-tv/u8500f-75-inch-crystal-uhd-4k-smart-tv-ua75u8500fkxxm | page_identity_or_price | Chưa xác minh được trang bán sản phẩm cụ thể. |
| https://www.samsung.com/my/tvs/uhd-4k-tv/u8500f-43-inch-crystal-uhd-4k-smart-tv-ua43u8500fkxxm | page_identity_or_price | Chưa xác minh được trang bán sản phẩm cụ thể. |
| https://www.samsung.com/nz/tvs/uhd-4k-tv/u8500f-55-inch-crystal-uhd-4k-smart-tv-ua55u8500fsxnz | concrete_offer | Model/variant discovery only; no verified concrete seller price. |
| https://www.samsung.com/au/business/tvs/uhd-4k-tv/u8500f-50-inch-crystal-uhd-4k-smart-tv-ua50u8500fwxxy | page_identity_or_price | Chưa xác minh được trang bán sản phẩm cụ thể. |
| https://www.samsung.com/nz/support/model/UA85U8500FSXNZ | page_identity_or_price | Chưa xác minh được trang bán sản phẩm cụ thể. |
| https://www.lg.com/sg/tvs-soundbars/4k-uhd-tvs/43ua7350psb | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://www.youtube.com/watch?v=wnESRUAcCbU&vl=en&xstg=CAMSBhUD-7L2Hw%3D%3D | source_type | Editorial/multiple-product search metadata. |
| https://www.lg.com/uk/tvs-soundbars/4k-uhd-tvs/50ua73006la | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://www.lg.com/nz/tv-soundbars/uhd-4k-tv/50ua7350psb | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://www.lg.com/nz/tv-soundbars/uhd-4k-tv/65ua7350psb | fetch_or_metadata | Title and direct URL must identify the same model/variant. |
| https://cellphones.com.vn/smart-tivi-samsung-uhd-55u8500f-4k-55-inch-2025.html | - | - |
| https://cellphones.com.vn/smart-tivi-samsung-uhd-50u8500f-4k-50-inch-2025.html | availability | Sản phẩm hiện không còn hàng. |
| https://cellphones.com.vn/smart-tivi-samsung-uhd-65u8500f-4k-65-inch-2025.html | - | - |
| https://laodong.vn/kinh-doanh/gia-xang-dau-hom-nay-209-quay-dau-giam-1769540.ldo | page_identity_or_price | Chưa xác minh được trang bán sản phẩm cụ thể. |
| https://www.youtube.com/watch?v=qhQeBBrbno4 | fetch_or_metadata | Title and direct URL must identify the same model/variant. |

### Image and session consistency checks

10/12 recommendation occurrences have an image; all 10 loaded. 8 unique URLs. TV images remain null. New Vision sport/Winner X/phone images were opened for visual inspection; other Vision images preserve the previously inspected same-page provenance. All 12 recommendation occurrences were fetched again with matching concrete offer prices. Persisted warnings equal POST warnings in all four sessions.
