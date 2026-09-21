# Live universal search — TV/phone regression

Ngày kiểm tra: 2026-09-20. Tiếp tục working tree hiện tại; không reset/undo/commit. Dữ liệu Live cuối được ghi riêng tại [LIVE_ELECTRONICS_CHECK.json](LIVE_ELECTRONICS_CHECK.json); báo cáo motorcycle trước được giữ nguyên.

## A. Phone regression root cause

Audit HTML thật trước sửa cho thấy Galaxy S24 Ultra (CellphoneS/Đức Huy Mobile) đã có Product identity, concrete Offer price và direct URL hợp lệ. Product JSON-LD thiếu `category`; H1 chỉ ghi model, path không có từ điện thoại. Tuy nhiên cả hai trang đều có `BreadcrumbList` chứa **Điện thoại / Điện thoại cũ**. Validator cũ chỉ xét schema/name/description/path, bỏ qua breadcrumb nên trả category null và hard filter loại candidate.

A56 vẫn được validator cũ nhận qua path `/dien-thoai-samsung-galaxy-a56.html`. Đây là thiếu lớp category evidence, không phải cần gán category từ requirement hoặc domain. S24 Ultra CellphoneS còn có OutOfStock; bổ sung category không được bỏ qua stock filter.

**Audit cuối bổ sung:** TechOne trả 3 A56 variants 7.880.000 / 8.990.000 / 9.690.000 đồng, có stock và cùng direct page, nhưng variant branch return trước helper. Cả 3 có category null và bị hard filter loại. Validator giờ gọi cùng helper sau khi variant identity/price đã được xác minh, trước khi trả offer; không sửa dealer parser. Giữ normalization category đã có của parser, bổ sung category thiếu từ parent đã verified. Variant có type trái parent bị loại riêng; form của related product vẫn bị chặn theo identity/action hiện có.

Đã fetch lại trực tiếp sau sửa cuối: cả ba A56 TechOne đều `category=điện thoại`, `category_source=breadcrumb`, `in_stock`, giá riêng không đổi. Honda Vision T&H trả lại đủ bốn phiên bản đúng giá với `category=xe máy`, `source=product_schema`. Đây là kiểm tra trang độc lập; số recommendation acceptance được tính từ bốn pipeline Live cuối, không cộng các offer kiểm tra riêng này vào kết quả search.

## B. TV regression root cause

Đã mở lại hai URL MediaMart Sony KD-50X80J/KD-65X80J trước sửa: validator hiện tại vẫn nhận Product, giá 9.990.000/10.990.000 và category tivi. Dealer parser không thay thế nhánh Product/ecommerce.

Live cũ không đi tới các URL này. Model hints bị lẫn mô tả (`Neo QLED 8K là chiếc TV`, tên nhiều hãng/tên kênh), query budget dành cho các hint kém và merchant queries không đa dạng. `TV` cũng chưa được coi cùng family với `tivi` trong hard filter/source strategy. Đây là các lỗi discovery/normalization, không phải lý do để nới sales-page validator.

## C. Category evidence helper

Helper mới `category_evidence.py` chỉ chạy quyết định category sau khi page/identity/concrete price đã được xác minh. Trả `category`, `source`, `confidence`, `reason`, `conflict` và observations cho audit.

Nhánh variant tái sử dụng normalization taxonomy đã có của parser đối với schema phân cấp. Điều này tránh false conflict giữa `Xe máy > Xe ga/Xe số` và breadcrumb `Xe máy`. Raw schema vẫn được giữ trong observations; không thay parser/giá/nhóm màu/tồn kho. Hai regression fixtures chứa cả taxonomy và HTML breadcrumb giống trang thật.

Hierarchy: **Product schema → breadcrumb → H1/title → verified URL path**. Breadcrumb hỗ trợ cả JSON-LD và HTML có scope breadcrumb; chọn category sâu nhất có thể nhận diện. Không dùng merchant domain. Nếu schema/breadcrumb/heading mâu thuẫn hoặc path thể hiện phụ kiện trái với main category, trả conflict và chặn offer. Nhánh search không được ghi đè quyết định này bằng category suy từ snippet.

TV/Tivi/Smart TV/Smart Tivi/Television cùng family `tivi`. Giá treo, remote, kệ, chân đế, phụ kiện, ốp lưng không được chuyển thành sản phẩm chính. Thiếu evidence vẫn unknown. Confidence là điểm rule, không phải xác suất thống kê.

## D. Model hint cleanup

Helper mới `model_hints.py` giữ brand/model xuất hiện liên tục trong title/snippet. Dừng ở marketing, price, đơn vị kích thước, newline; loại chuỗi số rời, nhiều brands ghép, phụ kiện và resolution đơn thuần 4K/8K. Tái sử dụng brand/product-family vocabulary hiện có; không cài tên model/seller riêng để ép Live PASS.

Mention trong bài viết chỉ được dùng để tạo lookup. Bản thân article, hint hoặc snippet không tạo offer. Product page vẫn phải qua identity, concrete price và category validation.

Query allocation gộp cách ghi cùng model khác RAM/dung lượng/connectivity để không tiêu hết slots vào một máy. Không gộp hoặc thay đổi offer/variant trong database. Model gốc được ưu tiên trước các phiên bản màu; bỏ marketing year và suffix review/marketing khỏi lookup.

Các discovery hints có cấu trúc cũng phải qua cleanup; không còn chuyển cả catalog heading kiểu `Samsung 55 Crystal UHD ... Smart TV` thành exact query. Chuỗi gộp nhiều model bằng dấu `/` bị loại; dạng dung lượng `8/128GB` vẫn hợp lệ. Tests kiểm tra cả raw mention lẫn structured discovery.

Dấu chấm kết thúc model không được kéo thêm câu kế tiếp vào query. News index được nhận diện bằng merchant-quality hiện có, không được ưu tiên hơn bài viết chỉ vì URL classifier trả UNKNOWN.

Loại suffix `Specs/Specifications/Features/Overview` khỏi hint. Khi phân bổ lượt exact sau, so sánh model key đã chuẩn hóa thay vì nguyên query string; `K80` và `K80 5G` không được chiếm hai slot “model chưa tìm”.

## E. Query allocation

Giới hạn lượt saved/requirement queries đầu còn tối đa 2; sau commerce pass vẫn có slots cho exact model và merchant. Queries exact generic có dạng `"brand model" mua`, `"brand model" giá bán`, và `site:domain "brand model" giá bán`; không ghép budget/purpose dài. Requirement context đầy đủ vẫn đi cùng diagnostics, eligibility/filter/scoring/ranking.

Merchant discovery nhận category aliases. Sau merchant/model queries, domain queries duyệt các merchants discover được và source-strategy hints hiện có; không tạo allowlist xác minh. Test với 20 saved queries và budget 8 chứng minh vẫn chạy model và merchant exact queries.

Merchant exact lookup có slot trước; các slot exact tiếp theo ưu tiên model chưa chạy ở model-discovery pass. Cách phân bổ này xử lý log Live cho thấy nhiều phiên bản cùng model hoặc cách ghi dung lượng đã lấn chỗ model khác.

## F. Motorcycle preserved / scope

Không sửa `dealer_offers.py`, budget semantics, weights, image policy hoặc database schema ở lượt này. Dealer variation/price/color/stock tests giữ nguyên. Additive budget table, snapshot/history/cache regression vẫn được chạy. Không đổi API/frontend routes, UI/dependency hoặc `.env`; mọi test/manual dùng DB tạm.

Các file sửa/tạo ở lượt này:

- `backend/app/services/extraction/category_evidence.py` (mới), `product_page_validator.py`.
- `backend/app/services/normalization/product_normalizer.py`, `filter/hard_filter.py`.
- `backend/app/services/search/model_hints.py` (mới), `progressive_retrieval.py`, `merchant_quality.py`, `source_strategy.py`, `search_service.py`, `retrieval_diagnostics.py`.
- `backend/scripts/check_live_sales.py` — thêm category provenance và ghi report riêng.
- `backend/tests/unit/test_category_evidence.py` (26 cases), `test_model_hints.py` (26 cases), `backend/tests/integration/test_electronics_retrieval.py` (3 cases) — mới.
- `backend/tests/unit/test_budget_retrieval.py` — query exact được phép ngắn, nhưng assertion kiểm tra đầy đủ budget/requirement context vẫn được giữ/thêm; không làm yếu business filter/score tests.
- `docs/ELECTRONICS_RETRIEVAL_REPORT.md`, `docs/LIVE_ELECTRONICS_CHECK.json`.

## G. Backend tests

`.venv\Scripts\python.exe -B -X utf8 -m pytest`: **500 collected / 500 passed / 0 failed / 2 warnings**, 18,94 giây. Chạy sau tất cả thay đổi validator/model hints; không dùng lại số 488/495/499 của source cũ. Warnings: Starlette/httpx deprecation; pytest không ghi được `.pytest_cache` do sandbox. Database sạch/tạm, không dùng `smart_shopping.db`.

Bao gồm test TV MediaMart mock và merchant phone mới: exact-model discovery → verified offer → category breadcrumb/path → recommendation có ảnh null/requirement unknown → GET giữ nguyên. Tests không gọi API thật.

Phone variant tests bao gồm: cả ba biến thể kế thừa breadcrumb và giữ giá riêng; related accessory form không nhận category; accessory type trong form bị loại, phone variants còn lại giữ nguyên; schema/breadcrumb conflict an toàn. Integration test đưa variant giá/stock thật qua candidate construction đến recommendation với camera/pin UNKNOWN và image null. Toàn bộ 45 dealer unit tests giữ nguyên và PASS.

## H. Frontend tests

`npm test`: **35/35 PASS**, 0 fail/skip. Node cảnh báo `MODULE_TYPELESS_PACKAGE_JSON` như trước.

## I. Lint/build

`npm run lint`: **PASS**, 0 errors/2 warnings cũ (compare useMemo, home navigation). `npm run build`: **PASS**, compile/TypeScript/static pages thành công.

## J. E2E

`npm run test:e2e`: **4/4 PASS**, 24,2 giây, Demo/local và DB tạm. Cảnh báo môi trường NO_COLOR/FORCE_COLOR, không test failure.

## K-N. Live final - 2026-09-20T16:35:01.621347+00:00

Run uses Live/Tavily and a temporary database. No previous scenario results are merged into these counts.

Counts below are summed per query (source occurrences, not unique URLs). total_filtered is the number remaining after hard filtering; hard-filtered is total_found minus total_filtered.

| Scenario | Queries | Tavily | DIRECT_PRODUCT | ARTICLE/NEWS/REVIEW | FETCH_BLOCKED | VERIFIED_CONTENT | VERIFIED_SEARCH_METADATA | Candidates | Hard-filtered | Remaining | Recommendations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 12 | 60 | 5 | 31 | 8 | 5 | 0 | 10 | 0 | 10 | 5 |
| B | 6 | 30 | 1 | 15 | 5 | 1 | 0 | 4 | 2 | 2 | 2 |
| C | 12 | 60 | 2 | 21 | 17 | 2 | 0 | 2 | 2 | 0 | 0 |
| D | 12 | 60 | 2 | 26 | 15 | 2 | 0 | 2 | 1 | 1 | 1 |

### A. Tôi cần xe máy khoảng 33 triệu để đi học, ưu tiên tiết kiệm xăng.

Checked: 2026-09-20T16:35:02.654053+00:00

Requirement/category:
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

Queries actually executed:
```text
requirement: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng mua giá bán Việt Nam
requirement: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng mua chính hãng
commercial: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng giá bán sản phẩm
commercial: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng mua online
model_discovery: "Honda Vision" mua
model_discovery: "Honda Click 125" mua
merchant_discovery: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng cửa hàng
merchant_discovery: xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng đại lý
merchant_products: site:hondath.vn "Honda Vision" giá bán
merchant_products: "Honda SH 350i" giá
merchant_products: "Honda Vision Promos" giá
merchant_products: site:hondath.vn xe máy giá khoảng 33000000 VND từ 31000000 đến 35000000 VND đi học tiêu thụ nhiên liệu tiết kiệm xăng giá bán
```

#### Recommendation 1

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
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 33000000,
  "PREFERRED_WINDOW": [
    31000000,
    35000000
  ],
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-cao-cap-mau-do-xam.png",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
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
  "SCORE": {
    "budget_score": 99.74,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 29.94
  },
  "MANUAL_PRICE": 32979273,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true
}
```

#### Recommendation 2

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
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2024/06/future-125fi-dac-biet-mau-bac-den-xam.jpg",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
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
  "SCORE": {
    "budget_score": 89.92,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 27.48
  },
  "MANUAL_PRICE": 32193818,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true
}
```

#### Recommendation 3

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
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": null,
  "IMAGE_LOADS": false,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-so/honda-future-125-fi",
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
  "SCORE": {
    "budget_score": 83.79,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 25.95
  },
  "MANUAL_PRICE": 31702909,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true
}
```

#### Recommendation 4

```json
{
  "NAME": "Honda Vision - dac biet",
  "BRAND": "Honda",
  "MODEL": "Vision",
  "VARIANT": {
    "attribute_pa_phien-ban": "dac-biet",
    "color_options": "nau-xam"
  },
  "PRICE": 34353818,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 33000000,
  "PREFERRED_WINDOW": [
    31000000,
    35000000
  ],
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-dac-biet-mau-nau-xam.png",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
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
  "SCORE": {
    "budget_score": 83.08,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 25.77
  },
  "MANUAL_PRICE": 34353818,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true
}
```

#### Recommendation 5

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
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 33000000,
  "PREFERRED_WINDOW": [
    31000000,
    35000000
  ],
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-tieu-chuan-mau-trang.png",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
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
  "SCORE": {
    "budget_score": 78.88,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 24.72
  },
  "MANUAL_PRICE": 31310182,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true
}
```

Provider query errors: []


### B. Tôi cần xe máy tối đa 33 triệu để đi học.

Checked: 2026-09-20T16:35:51.471834+00:00

Requirement/category:
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

Queries actually executed:
```text
requirement: xe máy giá dưới 33000000 VND đi học mua giá bán Việt Nam
requirement: xe máy giá dưới 33000000 VND đi học mua chính hãng
commercial: xe máy giá dưới 33000000 VND đi học giá bán sản phẩm
commercial: xe máy giá dưới 33000000 VND đi học mua online
model_discovery: "Honda Vision" mua
model_discovery: "Yamaha Janus" mua
```

#### Recommendation 1

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
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-cao-cap-mau-do-xam.png",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "SCORE": {
    "budget_score": 99.98,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 60.0
  },
  "MANUAL_PRICE": 32979273,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true,
  "HARD_MAX": 33000000
}
```

#### Recommendation 2

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
  "MERCHANT": "HEAD T&amp;H",
  "DOMAIN": "hondath.vn",
  "PRODUCT_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "CATEGORY": "xe máy",
  "CATEGORY_EVIDENCE_SOURCE": "product_schema",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://hondath.vn/wp-content/uploads/2026/05/vision-tieu-chuan-mau-trang.png",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://hondath.vn/xe-may/xe-ga/honda-vision",
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [],
  "SCORE": {
    "budget_score": 98.46,
    "requirement_score": 100.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 59.62
  },
  "MANUAL_PRICE": 31310182,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true,
  "HARD_MAX": 33000000
}
```

Provider query errors: []


### C. Tôi cần TV khoảng 10 triệu để xem phim.

Checked: 2026-09-20T16:36:23.848782+00:00

Requirement/category:
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

Queries actually executed:
```text
requirement: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua giá bán Việt Nam
requirement: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua chính hãng
commercial: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim giá bán sản phẩm
commercial: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim mua online
model_discovery: "Sony KD-43X81DK" mua
model_discovery: "Samsung UA55TU7000KXXV 4K" mua
merchant_discovery: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim cửa hàng
merchant_discovery: tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim đại lý
merchant_products: site:cellphones.com.vn "Sony KD-43X81DK" giá bán
merchant_products: "Sony KD-43X7000F" giá
merchant_products: "Samsung UA43NU7100KXXV" giá
merchant_products: site:cellphones.com.vn tivi giá khoảng 10000000 VND từ 9400000 đến 10600000 VND xem phim giá bán
```

No recommendation. Verified candidates rejected by hard filtering:

```json
{
  "NAME": "Smart Tivi Sony 4K 43 inch KD-43X81DK VN3",
  "URL": "https://cellphones.com.vn/smart-tivi-sony-4k-43-inch-kd-43x81dk.html",
  "PRICE": 19460000,
  "CATEGORY_DECISION": "tivi",
  "REJECT_STAGE": "availability",
  "REJECT_REASON": "Sản phẩm hiện không còn hàng."
}
```

```json
{
  "NAME": "Apple AirTag | Chính hãng Apple Việt Nam",
  "URL": "https://cellphones.com.vn/apple-airtag.html",
  "PRICE": 790000,
  "CATEGORY_DECISION": "phụ kiện",
  "REJECT_STAGE": "category",
  "REJECT_REASON": "Sản phẩm không đúng danh mục yêu cầu."
}
```

Provider query errors: []


### D. Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu.

Checked: 2026-09-20T16:36:53.041462+00:00

Requirement/category:
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

Clarification: chụp ảnh

Queries actually executed:
```text
requirement: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua giá bán Việt Nam
requirement: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua chính hãng
commercial: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt giá bán sản phẩm
commercial: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt mua online
model_discovery: "Redmi Note 14 6GB 128GB" mua
model_discovery: "Redmi K80 5G" mua
merchant_discovery: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt cửa hàng
merchant_discovery: điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt đại lý
merchant_products: site:cellphones.com.vn "Redmi Note 14" giá bán
merchant_products: "Redmi K808" giá
merchant_products: "REDMI K80 5G Smartphone" giá
merchant_products: site:cellphones.com.vn điện thoại giá khoảng 10000000 VND từ 9400000 đến 10600000 VND chụp ảnh pin pin lâu camera tốt giá bán
```

#### Recommendation 1

```json
{
  "NAME": "Xiaomi Redmi K80 5G (16GB - 1TB) - Chip Snapdragon 8 Gen 3",
  "BRAND": "Xiaomi",
  "MODEL": null,
  "VARIANT": {
    "sku": "xiaomi-redmi-k80-5g-16gb-1tb"
  },
  "PRICE": 12699000,
  "PRICE_TYPE": "CONCRETE",
  "AVAILABILITY": "in_stock",
  "BUDGET_MODE": "FLEXIBLE_TARGET",
  "TARGET": 10000000,
  "PREFERRED_WINDOW": [
    9400000,
    10600000
  ],
  "MERCHANT": "www.viettablet.com",
  "DOMAIN": "www.viettablet.com",
  "PRODUCT_URL": "https://www.viettablet.com/xiaomi-redmi-k80-5g-16gb-1tb",
  "CATEGORY": "điện thoại",
  "CATEGORY_EVIDENCE_SOURCE": "breadcrumb",
  "VERIFICATION_LEVEL": "VERIFIED_CONTENT",
  "PRODUCT_PAGE_CONFIDENCE": 95.0,
  "IMAGE_URL": "https://cdn.viettablet.com/images/detailed/65/xiaomi-redmi-k80-viettablet.jpg",
  "IMAGE_LOADS": true,
  "EVIDENCE_URL": "https://www.viettablet.com/xiaomi-redmi-k80-5g-16gb-1tb",
  "MATCHED": [],
  "UNMET": [],
  "UNKNOWN": [
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
  ],
  "SCORE": {
    "budget_score": 0.0,
    "requirement_score": 0.0,
    "purpose_score": 0.0,
    "rating_score": 0.0,
    "review_score": 0.0,
    "source_score": 50.0,
    "final_score": 5.0
  },
  "MANUAL_PRICE": 12699000,
  "SAME_OFFER_PRICE_CONFIRMED": true,
  "CONTENT_REOPEN_CONFIRMED": true
}
```

Provider query errors: []

Full source audit (QUERY, TITLE, SNIPPET, source type, identity/category/price evidence, rejection stage/reason) is in [LIVE_ELECTRONICS_CHECK.json](LIVE_ELECTRONICS_CHECK.json). Previous-check data in that file is historical only.

## O. Acceptance

**PARTIAL — lượt Live cuối chưa đạt đủ bốn scenario.**

- Motorcycle flexible: PASS, 5 recommendations từ 10 candidates; 5 giá nằm trong preferred window 31–35 triệu. Tiết kiệm xăng vẫn UNKNOWN, không tự nhận matched.
- Motorcycle hard max: PASS, 2 recommendations 31.310.182 / 32.979.273 đồng; 2 variant >33 triệu bị loại. Không bỏ hard max.
- TV: FAIL ở acceptance Live, 0 recommendation. Sony KD-43X81DK đã đúng category nhưng hết hàng; Apple AirTag là phụ kiện và bị loại đúng ở category. 12 queries/60 source occurrences chưa tìm được offer TV còn hàng đủ evidence. Không đưa offer MediaMart của lượt cũ vào kết quả hiện tại.
- Phone: PASS điều kiện valid direct offer, 1 Redmi K80 16GB/1TB từ Viettablet, 12.699.000 đồng, VERIFIED_CONTENT và category từ breadcrumb. Đây là **fallback ngoài preferred window 9,4–10,6 triệu**, không phải kết quả đáp ứng mức giá khoảng 10 triệu. Camera/pin thiếu evidence vẫn UNKNOWN. Budget score được giữ nguyên theo Python; không đổi semantics để ép fit.

Cả 8 recommendations được mở lại trang thật: identity/page và giá cùng offer đều khớp. 7 có image_url tải được (5 URL ảnh khác nhau); Future cao cấp giữ image null. Đã xem ảnh Vision, Future đặc biệt và Redmi K80 phù hợp model; ảnh K80 không thể tự chứng minh dung lượng RAM/storage, dung lượng lấy từ offer page. Thiếu ảnh không làm mất recommendation.

Gemini báo 429 quota (và có 503 trong các lượt kiểm tra trước); analyzer/explanation dùng local fallback theo config. Lượt cuối không có Tavily query error/timeout, nhưng có trang FETCH_BLOCKED ghi riêng trong diagnostics. Không dùng Demo products. Provider search trả kết quả thay đổi giữa các lượt; recall TV và lựa chọn gần budget cho phone vẫn cần cải thiện. Không khẳng định feature đã ổn định Live chỉ dựa vào automated PASS.

Known phone variant category bug đã được sửa và kiểm chứng riêng cả 3 A56 TechOne; A56 không xuất hiện trong recommendations của lượt cuối nên không được tính vào acceptance. Dừng tại đây với báo cáo PARTIAL; không sửa tiếp validator để nhận hàng hết stock/phụ kiện, không commit.

## P. Secret scan và Git review

Đã kiểm tra `git status --short`, `git diff --stat`, `git diff --check`. Working tree gồm 38 tracked modified và 37 untracked, 0 staged; đây là toàn bộ feature đang làm dở, không phải tất cả phát sinh ở lượt sửa cuối. Diff tracked: 593 insertions / 500 deletions; thống kê Git này không bao gồm untracked. `git diff --check` exit 0. Không reset/undo/commit.

`backend/.env` không tracked. Quét 214 text files của project và riêng 19 file docs Markdown/JSON (không có log file ngoài dependency/build directories): không thấy giá trị credential thật từ cấu hình hay mẫu credential có độ tin cậy cao; không có Bearer token dài trong docs/logs. Các pattern `api[_-]?key`, `authorization`, `bearer`, `secret`, `token` trong docs chỉ là tên biến, hướng dẫn và mô tả code. Có `SECRET_KEY` development trùng giá trị mẫu đã có sẵn trong README/config/examples/compose; không phải API key và không được thay đổi ở lượt này. Không in giá trị cấu hình ra báo cáo.
