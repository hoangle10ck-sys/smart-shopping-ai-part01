# Live universal product search — motorcycle continuation

Ngày kiểm tra: 2026-09-20. Tiếp tục working tree hiện tại, không reset/undo/commit. Kết quả Live và audit từng nguồn: [LIVE_MOTORCYCLE_CHECK.json](LIVE_MOTORCYCLE_CHECK.json). Báo cáo lượt trước được giữ riêng trong `LIVE_BUDGET_RETRIEVAL.md` và `LIVE_BUDGET_CHECK.json`.

**Kết luận cuối: dealer motorcycle acceptance PASS trong lượt Live này; toàn feature vẫn PARTIAL vì TV/phone chưa ổn định.** Backend 445/445, frontend 35/35, E2E 4/4, lint/build PASS. Live A/B/C/D lần lượt **3 / 5 / 0 / 0** recommendations.

## File sửa/tạo trong lượt tiếp tục này

| File | Thay đổi |
| --- | --- |
| `backend/app/services/extraction/dealer_offers.py` | Mới: đọc mapping variant → advertised price; gom màu cùng commercial version/giá, giữ màu khác giá; stock/unknown; ảnh variation có identity rõ; taxonomy dealer. |
| `backend/app/services/extraction/product_page_validator.py` | Tái sử dụng identity/source guards; xác minh từng variant; chọn H1 chính, thu thập breadcrumb/giá đề xuất/version cho discovery. |
| `backend/app/services/extraction/product_discovery.py` | Discovery brand/model/variant/range; breadcrumb chính + URL trùng model cho trang official thiếu Product schema; không tạo concrete offer từ MSRP/range. |
| `backend/app/services/search/progressive_retrieval.py` | Exact model/dealer queries, readiness từng offer, giữ requirement context và chẩn đoán từng variant; MSRP của một version không loại ưu tiên toàn model. |
| `backend/app/services/search/merchant_quality.py` | Merchant discovery dùng source evidence, tránh tag/news indexes. |
| `backend/app/services/search/retrieval_diagnostics.py` | Mới: ghi các trường source/identity/category/availability/rejection theo từng query và offer/hint. |
| `backend/app/services/search/search_service.py` | Một source URL có thể sinh nhiều concrete variant candidates. |
| `backend/app/services/dedup/product_deduplicator.py` | Không gộp mất những variant có identity khác nhau. |
| `backend/app/models/__init__.py` | Import/export rõ `RequirementBudget` cho initialization. |
| `backend/scripts/check_live_sales.py` | Bốn scenario Live mới, DB tạm, diagnostics + budget + variant + kiểm tra lại URL/giá/ảnh. |
| `backend/tests/unit/test_dealer_offers.py` | Mới: 45 cases về price mapping, màu, availability, ảnh, source guards, taxonomy, schema-year/financing identity và official discovery. |
| `backend/tests/unit/test_progressive_retrieval.py`, `backend/tests/unit/test_budget_retrieval.py` | Regression cho suggested price, query ngắn, model hint từ tiêu đề và giữ budget/requirement context sau discovery. |
| `backend/tests/integration/test_dealer_variant_pipeline.py` | Mới: tách 3 variant, flexible ranking, hard-max, cập nhật offer và đọc lại snapshot/history. |
| `backend/tests/integration/test_budget_table_compatibility.py` | Mới: SQLite cũ, additive init, không backfill; cache key ba budget modes. |
| `docs/MOTORCYCLE_RETRIEVAL_REPORT.md`, `docs/LIVE_MOTORCYCLE_CHECK.json` | Báo cáo này và dữ liệu Live thực tế. |

Các thay đổi feature từ những lượt trước trong Git diff được giữ nguyên; bảng trên chỉ mô tả lượt tiếp tục tập trung xe máy. Không sửa frontend/dependency/routes ở lượt này.

## D. Flexible/hard budget

Giữ nguyên 6%, rounding/caps hiện tại. Target 33.000.000 → preferred window **31.000.000–35.000.000 VND**. Ngoài window vẫn có thể là fallback, giảm price fit; không đổi thành hard filter. `HARD_MAX` 33.000.000 loại mọi offer lớn hơn mức đó. `RANGE` giữ giới hạn min/max. Không đổi weights **25/30/20/10/5/10**; Python quyết định score.

## Budget metadata persistence

Bảng phụ `requirement_budgets` đã được thêm ở lượt trước; lượt này xác nhận import và thử `init_db()` hai lần trên **SQLite cũ giả lập** chưa có bảng. Kết quả: bảng được tạo bổ sung, dữ liệu cũ giữ nguyên, bảng metadata không có dòng backfill. Session cũ không metadata giữ semantics legacy; session mới ghi/đọc mode/window. Cache key phân biệt ba mode. Snapshot/history giữ mode/window và giá variant lịch sử khi session khác cập nhật offer.

Không thêm bảng/cột mới ở lượt này. Không chạy init/backfill/migration trên database thật. API routes không đổi; variant đã dùng metadata JSON/schema tùy chọn của feature hiện tại.

## Category fallback safety

Category lấy từ product evidence đã xác minh; chỉ fallback URL path khi product data chưa có category. Không dùng requirement/domain để gán category. Regression xác nhận TV không thành phone dù path chứa `dien-thoai`, giá treo TV vẫn là phụ kiện, domain chung không làm category unknown thành phone, trang chưa verified không được suy category từ path.

## A. Dealer variation parser và root cause

Các trang thực tế có hai tình huống mà pipeline trước chưa xử lý:

1. Trang model official thiếu Product schema/H1 dùng được, chỉ có breadcrumb model, version selector và giá đề xuất. Ví dụ Honda Vision: giá một version đang chọn không phải giá bán của tất cả phiên bản. Nay thu thập discovery từ breadcrumb khớp URL + brand trên trang; không biến thành recommendation.
2. Trang dealer có AggregateOffer và các concrete prices trong form `data-product_variations`, nhưng pipeline trước chỉ thấy range. HEAD T&H Wave Alpha/Winner X có mapping phiên bản/màu → giá bán, `is_purchasable`, `variation_is_active`, tồn kho. Nay đọc đúng mapping từng variant, không lấy minimum range.

3. HEAD T&H Vision: H1 `Honda Vision`, Product schema có thêm `2026` và marketing suffix. Kiểm tra identity cũ loại schema trước khi đọc variations. Ngoại lệ mới chỉ nhận năm xuất hiện riêng trong schema khi `mainEntityOfPage` trỏ đúng URL hiện tại, H1 khớp URL và không có năm mâu thuẫn. Không bỏ qua model/capacity/version khác nhau.
4. Taxonomy `Xe máy &gt; Xe ga` không khớp category canonical. Chỉ chuẩn hóa các subtype xe rõ (`Xe ga`, `Xe số`, `Xe côn tay`) của taxonomy source đã verified; không nhận nhánh phụ kiện làm xe máy.
5. HEAD T&H Future: schema suffix `trả góp 0%` bị coi là model số 0; H1 `125FI` khác định dạng URL `125-fi`. Khi có `mainEntityOfPage` đúng URL, chuẩn hóa riêng FI spacing và bỏ đúng cụm financing 0%; model/capacity/variant/năm mâu thuẫn vẫn bị từ chối.

## C. Exact-model retrieval

Đối chiếu Live: query `"Honda Vision" mua` trả direct dealer pages T&H và Hưng Thành Đạt; query dài kèm budget/purpose quay lại bài/video tư vấn. Nay query exact-model chỉ chứa model + hành động mua/giá/đại lý và domain khi phù hợp. Budget/purpose/requirements vẫn áp dụng ở eligibility, scoring, ranking và được ghi trong diagnostics. Truy vấn discovery theo nhu cầu ban đầu vẫn có budget/purpose. Không cài danh sách Honda/Yamaha riêng. Model hint suy từ snippet phải xuất hiện nguyên văn trong title/content, model bắt đầu bằng chữ, không ghép nhiều hãng, giới hạn số token; tránh lấy timestamp thành model giả. Đây chỉ là hint để lookup, không phải verified identity/offer. Tests bảo vệ cả hint có thật trong snippet và hai trường hợp false positive số/nhiều hãng.

## B. Variant identity và safety

- Form phải thuộc URL hiện tại, có product ID, active/purchasable, thuộc tính variant không rỗng, giá dương và currency VND xác định.
- Bảng giá phải chỉ rõ sản phẩm qua `data-product`/caption, cột variant và một cột giá bán, một amount/cell; trang có hành động đặt xe/liên hệ mua. Không bắt buộc cart.
- Bỏ mapping xung đột giá cho cùng variant, range chưa xác định, form sản phẩm liên quan và trang news/review/category/home/search.
- Commercial version/capacity/spec khác nhau giữ identity riêng. Cùng version và cùng giá: gộp các màu tương đương, không tạo bản sao chỉ do màu. Nếu màu có giá khác thì giữ riêng. Khi stock khác nhau, chỉ liệt kê các màu cùng trạng thái tốt nhất có evidence; không coi màu hết hàng là còn hàng.
- Variant có price riêng và signature riêng khi dedup; source/evidence vẫn cùng direct dealer page. Ảnh gắn ngay trong variation chỉ được thử tải sau khi offer verified, với model/version/màu khớp metadata/filename. Ảnh không chắc để null; thiếu ảnh không loại offer.
- Dữ liệu nguồn lỗi không được sửa đoán: trang Vario kiểm tra có một `display_price=409990000`; hệ thống không tự hạ xuống 40.999.000. Trang Phát Tiến SH160i có giá variant trống vẫn không sinh offer.

## E. Availability

`is_in_stock=true` → `in_stock`; false → `out_of_stock` và hard filter loại khỏi recommendation; thiếu/null → unknown, không tự suy hết hàng. Tests kiểm tra cả ba và trường hợp một màu hết hàng, màu khác còn hàng.

## F. Full backend tests

Lệnh: `.venv\Scripts\python.exe -B -X utf8 -m pytest` trong `backend`.

**445 collected / 445 passed / 0 failed / 2 warnings**, 17,66 giây, sau tất cả sửa code cuối. Hai warnings: Starlette deprecates httpx TestClient; pytest không ghi được `.pytest_cache` do quyền sandbox. Test database tạm, không dùng `smart_shopping.db`.

Bao gồm regression Phase 1–6: search failure giữ kết quả/warnings, category/value/weight/budget analyzer, snapshot, LLM fallback, structured evidence/matches, history/cache. Không xóa hoặc làm yếu test.

## G. Frontend final tests

`npm test`: **35 tests / 35 passed / 0 failed / 0 skipped**. Node có cảnh báo `MODULE_TYPELESS_PACKAGE_JSON`; không đổi dependency/package type ngoài phạm vi.

## H. Lint/build

- `npm run lint`: **PASS**, 0 errors, 2 warnings cũ (`compare/[comparisonId]/page.tsx:149` useMemo; `app/page.tsx:397` navigation).
- `npm run build`: **PASS**, compile, TypeScript và generate pages thành công.

## I. E2E

`npm run test:e2e`: **4/4 PASS**, 19,6 giây, sau sửa cuối, Demo/local backend + database tạm. Bao gồm home→analysis→search→results→filter/detail/compare/feedback/history, structured evidence, legacy snapshot/warning, sales-link/image fallback. Chỉ có cảnh báo môi trường `NO_COLOR`/`FORCE_COLOR`.

## J-M. Final Live verification

Live Tavily, backend/.env, isolated temporary SQLite. UTC timestamps are in the JSON; local time is UTC+7. Counts below use unique source URLs; variants are counted as candidates.

| Scenario | Queries | Tavily raw | Unique URLs | Direct pages | Article / news / review | Fetch blocked | Verified content / metadata | Candidates | Hard-filter rejected | Recommendations |
| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: |
| A | 12 | 60 | 38 | 1 | 7 / 11 / 0 | 9 | 1 / 0 | 3 | 0 | 3 |
| B | 6 | 30 | 22 | 2 | 6 / 5 / 0 | 3 | 2 / 0 | 7 | 2 | 5 |
| C | 12 | 60 | 37 | 0 | 6 / 3 / 1 | 14 | 0 / 0 | 0 | 0 | 0 |
| D | 12 | 60 | 42 | 3 | 10 / 10 / 1 | 14 | 3 / 0 | 3 | 3 | 0 |

### J. Flexible motorcycle

Tôi cần xe máy khoảng 33 triệu để đi học, ưu tiên tiết kiệm xăng.

Checked at: 2026-09-20T06:37:56.087651+00:00

Requirement:

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
      "name": "fuel_efficiency",
      "value": "tiết kiệm xăng",
      "priority": 4
    }
  ],
  "excluded_requirements": [],
  "sort_preference": "best_match",
  "confidence": 0.95
}
```

Queries executed:

- `xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng mua giá bán Việt Nam`
- `xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng mua chính hãng`
- `xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng giá bán sản phẩm`
- `xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng mua online`
- `"Honda Future" mua`
- `xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng cửa hàng`
- `xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng đại lý`
- `site:honda.com.vn "Honda Future 125 FI" giá bán`
- `site:honda.com.vn xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng giá bán`
- `"Honda Future 125 FI" mua chính hãng`
- `"Honda Future 125 FI Phiên bản Đặc biệt" mua chính hãng`
- `"Honda Future 125 FI Phiên bản Cao cấp" mua chính hãng`

Recommendation 1:

```json
{
  "NAME": "Honda Future 125FI - dac biet",
  "BRAND": "Honda",
  "MODEL": "Future 125FI",
  "VARIANT": {
    "attribute_pa_phien-ban": "dac-biet",
    "color_options": "bac-den-xam / xanh-den-bac"
  },
  "PRICE": 32193818,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 33000000,
  "PREFERRED_WINDOW": [
    31000000,
    35000000
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [
    {
      "name": "fuel_efficiency",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ],
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2024/06/future-125fi-dac-biet-mau-bac-den-xam.jpg",
  "IMAGE_LOADS": true,
  "IMAGE_SOURCE": "product_variation_image",
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 89.92,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 27.48
  }
}
```

Recommendation 2:

```json
{
  "NAME": "Honda Future 125FI - cao cap",
  "BRAND": "Honda",
  "MODEL": "Future 125FI",
  "VARIANT": {
    "attribute_pa_phien-ban": "cao-cap",
    "color_options": "do-den-trang / trang-den-do / xam-den-xanh"
  },
  "PRICE": 31702909,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 33000000,
  "PREFERRED_WINDOW": [
    31000000,
    35000000
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [
    {
      "name": "fuel_efficiency",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ],
  "IMAGE_URL": null,
  "IMAGE_LOADS": false,
  "IMAGE_SOURCE": null,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 83.79,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 25.95
  }
}
```

Recommendation 3:

```json
{
  "NAME": "Honda Future 125FI - tieu chuan",
  "BRAND": "Honda",
  "MODEL": "Future 125FI",
  "VARIANT": {
    "attribute_pa_phien-ban": "tieu-chuan",
    "color_options": "xanh-den"
  },
  "PRICE": 30524727,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 33000000,
  "PREFERRED_WINDOW": [
    31000000,
    35000000
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [
    {
      "name": "fuel_efficiency",
      "requested_value": "tiết kiệm xăng",
      "product_value": null,
      "status": "unknown",
      "reason": "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu."
    }
  ],
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2024/06/future-125fi-tieu-chuan-mau-xanh-den.jpg",
  "IMAGE_LOADS": true,
  "IMAGE_SOURCE": "product_variation_image",
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 69.06,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 22.26
  }
}
```

### K. Hard-max motorcycle

Tôi cần xe máy tối đa 33 triệu để đi học.

Checked at: 2026-09-20T06:38:33.967397+00:00

Requirement:

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

Queries executed:

- `xe máy giá dưới 33000000 VND đi học mua giá bán Việt Nam`
- `xe máy giá dưới 33000000 VND đi học mua chính hãng`
- `xe máy giá dưới 33000000 VND đi học giá bán sản phẩm`
- `xe máy giá dưới 33000000 VND đi học mua online`
- `"Honda Future" mua`
- `"Honda Vision" mua`

Recommendation 1:

```json
{
  "NAME": "Honda Vision - cao cap",
  "BRAND": "Honda",
  "MODEL": "Vision",
  "VARIANT": {
    "attribute_pa_phien-ban": "cao-cap",
    "color_options": "do-xam"
  },
  "PRICE": 32979273,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "HARD_MAX",
  "TARGET": null,
  "PREFERRED_WINDOW": [
    null,
    null
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-cao-cap-mau-do-xam.png",
  "IMAGE_LOADS": true,
  "IMAGE_SOURCE": "product_variation_image",
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 99.98,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 60.0
  }
}
```

Recommendation 2:

```json
{
  "NAME": "Honda Future 125FI - dac biet",
  "BRAND": "Honda",
  "MODEL": "Future 125FI",
  "VARIANT": {
    "attribute_pa_phien-ban": "dac-biet",
    "color_options": "bac-den-xam / xanh-den-bac"
  },
  "PRICE": 32193818,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "HARD_MAX",
  "TARGET": null,
  "PREFERRED_WINDOW": [
    null,
    null
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2024/06/future-125fi-dac-biet-mau-bac-den-xam.jpg",
  "IMAGE_LOADS": true,
  "IMAGE_SOURCE": "product_variation_image",
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 99.27,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 59.82
  }
}
```

Recommendation 3:

```json
{
  "NAME": "Honda Future 125FI - cao cap",
  "BRAND": "Honda",
  "MODEL": "Future 125FI",
  "VARIANT": {
    "attribute_pa_phien-ban": "cao-cap",
    "color_options": "do-den-trang / trang-den-do / xam-den-xanh"
  },
  "PRICE": 31702909,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "HARD_MAX",
  "TARGET": null,
  "PREFERRED_WINDOW": [
    null,
    null
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "IMAGE_URL": null,
  "IMAGE_LOADS": false,
  "IMAGE_SOURCE": null,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 98.82,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 59.71
  }
}
```

Recommendation 4:

```json
{
  "NAME": "Honda Vision - tieu chuan",
  "BRAND": "Honda",
  "MODEL": "Vision",
  "VARIANT": {
    "attribute_pa_phien-ban": "tieu-chuan",
    "color_options": "trang-den"
  },
  "PRICE": 31310182,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "HARD_MAX",
  "TARGET": null,
  "PREFERRED_WINDOW": [
    null,
    null
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-tieu-chuan-mau-trang.png",
  "IMAGE_LOADS": true,
  "IMAGE_SOURCE": "product_variation_image",
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 98.46,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 59.62
  }
}
```

Recommendation 5:

```json
{
  "NAME": "Honda Future 125FI - tieu chuan",
  "BRAND": "Honda",
  "MODEL": "Future 125FI",
  "VARIANT": {
    "attribute_pa_phien-ban": "tieu-chuan",
    "color_options": "xanh-den"
  },
  "PRICE": 30524727,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "HARD_MAX",
  "TARGET": null,
  "PREFERRED_WINDOW": [
    null,
    null
  ],
  "MERCHANT": "HEAD T&H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "CONFIDENCE": 95.0,
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2024/06/future-125fi-tieu-chuan-mau-xanh-den.jpg",
  "IMAGE_LOADS": true,
  "IMAGE_SOURCE": "product_variation_image",
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "PRODUCT_PAGE_VALID": true,
  "MANUAL_PRICE_MATCHES": true,
  "SCORE": {
    "budget_score": 97.75,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 59.44
  }
}
```

### L. TV

Tôi cần TV khoảng 10 triệu để xem phim.

Checked at: 2026-09-20T06:39:07.140483+00:00

Requirement:

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

Queries executed:

- `tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua giá bán Việt Nam`
- `tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua chính hãng`
- `tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim giá bán sản phẩm`
- `tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua online`
- `"Samsung Neo QLED 8K là chiếc TV" mua`
- `"Samsung U8500F LG UA7350 TCL P7K Xiao" mua`
- `tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim cửa hàng`
- `tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim đại lý`
- `site:cellphones.com.vn "Samsung Neo QLED 8K là chiếc TV" giá bán`
- `site:cellphones.com.vn tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim giá bán`
- `"Samsung Neo QLED 8K là chiếc TV" mua chính hãng`
- `"Samsung U8500F LG UA7350 TCL P7K Xiao" mua chính hãng`

**0 recommendations.** See rejection analysis below and per-source `source_audit` in the JSON.

### M. Phone

Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu.

Checked at: 2026-09-20T06:39:32.441982+00:00

Clarification: chụp ảnh

Requirement:

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

Queries executed:

- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua giá bán Việt Nam`
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua chính hãng`
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt giá bán sản phẩm`
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua online`
- `"Samsung Galaxy S24. Galaxy S24 ấy thì" mua`
- `"Samsung Galaxy A56 5G Buy genuine HONOR" mua`
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt cửa hàng`
- `điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt đại lý`
- `site:cellphones.com.vn "Samsung Galaxy S24 Ultra 12GB 256GB" giá bán`
- `site:cellphones.com.vn điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt giá bán`
- `"Samsung Galaxy S24 Ultra 12GB 256GB" mua chính hãng`
- `"Samsung Galaxy S24 | S24+" mua chính hãng`

**0 recommendations.** See rejection analysis below and per-source `source_audit` in the JSON.

## N. PASS hay PARTIAL

**Dealer motorcycle: PASS theo acceptance về Live offer.** A có 3 Future variants, B có 5 Future/Vision variants. Tất cả có model, commercial version, concrete advertised price, merchant, direct URL và `VERIFIED_CONTENT`; mở lại trang xác nhận đúng giá từng variant. Không dùng minimum AggregateOffer. B loại Vision Đặc biệt 34.353.818 và Thể thao 36.612.000 vì vượt 33 triệu. A giữ Future Tiêu chuẩn 30.524.727 như fallback ngoài preferred window; price fit thấp hơn hai phiên bản trong window.

**Toàn feature: PARTIAL.** Không xác nhận TV/phone Live PASS bằng kết quả cũ. Automated regression PASS không chứng minh chất lượng recall của provider ở mọi lượt Live.

## O. Giới hạn còn lại và chẩn đoán

1. **TV:** mất trước candidate extraction. 60 Tavily results, 37 URL riêng, không có direct offer verified; 14 URL bị fetch blocked. Nhiều nguồn là category, bài/video hoặc metadata không đủ identity/giá bán. Query model hint vẫn có thể chứa mô tả không phải model chính xác, tiêu tốn query budget. Trong lượt trước có TV recommendations, nhưng lượt cuối này là 0; không khẳng định đã ổn định.
2. **Phone:** 3 concrete seller pages được verified nhưng category vẫn null, cả 3 bị loại ở stage `category`. Không gán category từ requirement hay từ domain. Cụ thể:

| Sản phẩm | Merchant / URL | Giá | Availability | Lý do cuối |
| --- | --- | ---: | --- | --- |
| Galaxy S24 Ultra 12GB/256GB | [CellphoneS](https://cellphones.com.vn/samsung-galaxy-s24-ultra.html) | 25.290.000 | OutOfStock | Category unknown; còn có stock không phù hợp, dù filter dừng ở category trước. |
| Galaxy S24 Ultra 5G 12GB/256GB cũ | [Đức Huy Mobile](https://www.duchuymobile.com/samsung-galaxy-s24-ultra-5g-cu) | 10.599.000 | InStock | Category unknown. |
| Galaxy S24 Plus 12GB/256GB | [CellphoneS](https://cellphones.com.vn/samsung-galaxy-s24-plus.html) | 15.690.000 | InStock | Category unknown. |

3. **Requirement evidence:** A không có số liệu fuel consumption được parser trích xuất đủ để đối chiếu, nên `fuel_efficiency=unknown`, không matched/unmet. Các recommendation là offer phù hợp budget theo dữ liệu có sẵn, chưa chứng minh “tiết kiệm xăng”. B không có requirement item cụ thể nên matched/unmet/unknown đều rỗng; không suy thêm tiêu chí từ frontend.
4. **Ảnh:** Future Đặc biệt màu bạc/xám, Tiêu chuẩn xanh/đen và Vision Cao cấp đỏ/xám, Tiêu chuẩn trắng/đen đã được xem trực quan, phù hợp model và màu trong variation nguồn; ảnh đều tải được. Future Cao cấp không có image đủ bằng chứng, giữ null và vẫn được recommend. `image_loads=false` khi URL null nghĩa là không có ảnh để kiểm tra, không phải offer lỗi.
5. **Provider:** lượt cuối không có Tavily query error/timeout/quota, nhưng có các page fetch blocked như bảng thống kê. Gemini báo **429 RESOURCE_EXHAUSTED**, free-tier limit 20 cho model được cấu hình; analysis/clarification dùng local fallback, explanation `fallback`. Có 503 ở một lượt điều tra trước, không phải lỗi Tavily. Không dùng Demo products để bù Live.
6. **Parser boundaries:** chỉ xử lý các mapping rõ từ main-product form/bảng giá. Trang chỉ có range, JS không cung cấp dữ liệu đọc được, bảng nhiều model hoặc identity chưa đủ vẫn bị loại. Giá là advertised price tại thời điểm kiểm tra, không tự cộng phí đăng ký/lăn bánh. Confidence 95 là điểm rule của validator, không phải xác suất xác nhận độc lập.
7. **Display metadata:** merchant nguồn còn HTML entity (`HEAD T&amp;H`) trong API/JSON; bảng recommendation trong báo cáo giải mã để dễ đọc. Không mở thêm thay đổi UI ngoài phạm vi.

Các trường `QUERY/TITLE/DOMAIN/URL/SOURCE_TYPE/BRAND/MODEL/VARIANT/PRICE_TYPE/PRICE/PRICE_MIN/PRICE_MAX/PAGE_VERIFICATION/IDENTITY_STATUS/CATEGORY_STATUS/AVAILABILITY_STATUS/REJECT_STAGE/REJECT_REASON` của từng quan sát nằm trong `scenarios[].source_audit` của JSON đi kèm. Source counts đếm URL; candidate/recommendation counts đếm commercial variants. `total_filtered` trong API là số còn lại sau hard filter, không phải số bị loại.

Không đổi budget tolerance/weights, API/frontend routes, History/Cache semantics hoặc database schema mới. Không backfill/đụng database thật, không sửa `.env` hay dependency. Giữ các thay đổi hợp lệ trước đó. Không commit/reset/undo. Dừng sau báo cáo này.
