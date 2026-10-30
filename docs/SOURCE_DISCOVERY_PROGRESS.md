# Tiến độ kiến trúc phát hiện nguồn và thu thập sản phẩm

Ngày khởi tạo: 2026-10-29
Mục tiêu: theo dõi lộ trình từ khám phá URL mới đến thu thập sản phẩm/Offer có bằng chứng. File này là bảng tiến độ tổng hợp của lộ trình; tiêu chí kỹ thuật chi tiết và test vẫn nằm trong [TASKS.md](../TASKS.md), [TASKS_UNIFIED_SEARCH.md](../TASKS_UNIFIED_SEARCH.md), [CRAWLER_RUNBOOK.md](CRAWLER_RUNBOOK.md) và [CRAWLER_PROGRESS.md](CRAWLER_PROGRESS.md).

## Quy tắc cập nhật

- Sau mỗi giai đoạn, cập nhật trạng thái, bằng chứng và ngày hoàn thành trong bảng; thêm một mục vào nhật ký thay đổi bên dưới, không xóa checkpoint cũ.
- Chỉ đánh dấu `DONE` khi tiêu chí giai đoạn có bằng chứng kiểm chứng được. Phân biệt kiểm thử offline với xác minh nguồn Live.
- Kết quả SearXNG/Tavily là URL ứng viên, không tự trở thành Product hoặc Offer.
- Nguồn mới chỉ được crawl sau khi có quyết định cho phép theo chính sách nguồn. Điểm tin cậy không thay thế quyền thu thập.
- Giữ nguyên Product/Variant, Offer, provenance, thời điểm quan sát và snapshot hiện có. Không dùng dữ liệu Research làm giá bán Live.

## Trạng thái hiện tại

| Giai đoạn | Kết quả cần đạt | Trạng thái | Bằng chứng và việc còn lại |
|---|---|---|---|
| 1. Nối SearXNG vào FastAPI ở chế độ khám phá | Backend truy vấn endpoint nội bộ; trả URL ứng viên, tên miền và trạng thái nguồn; có timeout/lỗi rõ ràng. | `DONE` | 2026-10-29: tích hợp `web_discovery` riêng, không đưa URL ứng viên vào pipeline tải trang/ghi Product hoặc Offer. Test mục tiêu 25 passed; smoke qua FastAPI với SearXNG cục bộ trả HTTP 200 và 6 URL ứng viên, Product/Offer không đổi. Endpoint vẫn chưa bật trong runtime Compose mặc định. Đây là xác minh khám phá Live, không xác minh giá/tồn kho/sản phẩm. |
| 2. Quản lý ứng viên và trạng thái nguồn | Phân biệt `DISCOVERED`, `REVIEW_REQUIRED`, `APPROVED`, `RESTRICTED`/`DISABLED`; chỉ nguồn được duyệt mới vào collector. | `DONE` | 2026-10-29: URL ứng viên mang `DISCOVERED` và trạng thái rà soát được suy ra từ registry JSON hiện có. `collector_eligible=true` chỉ khi registration `approved` + `enabled`, hai cờ collector cùng bật, nguồn là `product_page`, URL dùng HTTPS/port chuẩn và path nằm trong allowlist. Trạng thái ứng viên được lưu trong snapshot tìm kiếm hiện có; không thêm schema. Smoke với registry rỗng trả 7 URL, tất cả `REVIEW_REQUIRED`, không URL nào đủ điều kiện collector, Product/Offer không đổi. Việc duyệt vẫn là thao tác cấu hình vận hành; chưa có màn hình quản trị. |
| 3. Duyệt một nguồn cụ thể | Có ít nhất một nguồn với quyền truy cập, điều khoản, robots, giới hạn và phương thức truy cập được rà soát. | `BLOCKED` | 2026-10-29: đã đánh giá Open Food Facts/Open Products Facts như nguồn Research, không phải nguồn giá/Offer. Chưa nhập dữ liệu vì phải chốt nghĩa vụ attribution/share-alike, thông tin định danh API và điều khoản cụ thể của OPF. Không có nguồn thương mại nào trong registry được duyệt; không tự bật Shopee/Lazada. |
| 4. Pilot collector giới hạn | Chạy preflight và smoke test có giới hạn trên 20–50 URL từ nguồn được duyệt; ghi số URL, kết quả và lỗi. | `BLOCKED` | Phụ thuộc giai đoạn 3. Live smoke chưa chạy; không có URL sản phẩm Live được xác minh trong lần kiểm tra này. Tiêu chí T09 và lệnh vận hành nằm trong [TASKS.md](../TASKS.md) và [runbook](CRAWLER_RUNBOOK.md). |
| 5. Kiểm chứng, lưu dữ liệu và nối vào đề xuất | Product/Variant tách biệt Offer; bằng chứng theo trường; giá/tồn kho có nguồn và thời điểm; tích hợp DB → recommendation → snapshot. | `OFFLINE_TESTED` | Mã và test offline cho collector, persistence, provenance và tích hợp recommendation đã được ghi nhận trong [CRAWLER_PROGRESS.md](CRAWLER_PROGRESS.md) và T03–T08. Chưa được xác minh với nguồn thương mại Live; chỉ nâng trạng thái sau pilot thực tế. |
| 6. Mở rộng nguồn và danh mục | Mở rộng theo chất lượng pilot, độ mới, giới hạn từng nguồn và ngân sách vận hành. | `NOT_STARTED` | Chưa đặt số lượng nguồn/sản phẩm Live làm cam kết. Chỉ mở rộng sau khi pilot đạt tiêu chí chất lượng và quyền truy cập. |

### Trạng thái dữ liệu cần phân biệt

- Khả năng khám phá SearXNG qua FastAPI: `LIVE_VERIFIED` trong smoke test cô lập ngày 2026-10-29; HTTP 200, có URL ứng viên, Product/Offer không thay đổi. Runtime Compose mặc định chưa cấu hình endpoint.
- Khả năng tìm kiếm SearXNG trực tiếp: `LIVE_VERIFIED` cho truy vấn JSON của SearXNG ngày 2026-10-29; **không** chứng minh trang sản phẩm đã được đọc hoặc giá/tồn kho/đánh giá đã xác minh.
- Collector sản phẩm thương mại trong runtime: `LIVE_NOT_VERIFIED`.
- Research catalog ABO: `RESEARCH_DATASET_VERIFIED`, không phải Offer/giá bán Live. Checkpoint ngày 2026-10-29 ghi nhận 200 ABO ResearchProduct, 184 có ảnh và 0 historical price trong [RESEARCH_DATA_PROGRESS.md](RESEARCH_DATA_PROGRESS.md).
- Test collector: `OFFLINE_TESTED` theo checkpoint tài liệu; không tính fixture/mock là xác minh Live.

## Điều kiện nghiệm thu cuối lộ trình

- Ít nhất một nguồn được duyệt, có URL/trang thật và bằng chứng chính sách truy cập được ghi lại.
- Có thể tái lập luồng khám phá → policy gate → fetch → parse → kiểm chứng → lưu → recommendation.
- Báo cáo số lượng URL đã thử, URL sản phẩm hợp lệ, Product/Variant/Offer lưu thành công, trường giá/định danh có bằng chứng và lỗi bị hạn chế; mọi tỷ lệ có mẫu số.
- Không biến URL tìm kiếm, dữ liệu Research, fixture hoặc snippet thành giá/tồn kho/đánh giá Live.
- Unit/integration/API/regression tests, lint, type-check, build và E2E phù hợp đều có lệnh cùng exit code thực tế; kiểm tra Git diff trước khi kết thúc.

## Nhật ký cập nhật

### 2026-10-29 — Khởi tạo tracker

- Khảo sát tài liệu, cấu hình runtime backend và dịch vụ SearXNG ở chế độ chỉ đọc.
- Truy vấn trực tiếp SearXNG `laptop Việt Nam`: HTTP 200, JSON, 38 kết quả. Không crawl trang sản phẩm.
- Runtime backend: `collector_live_enabled=false`, `collector_policy_confirmed=false`, registry 0 nguồn, endpoint SearXNG chưa cấu hình, Tavily chưa cấu hình.
- Kết luận: khám phá trực tiếp qua SearXNG hoạt động; tích hợp backend chưa xong; thu thập thương mại Live vẫn `LIVE_NOT_VERIFIED`.
- Thay đổi code/database: không có.

### 2026-10-29 — Hoàn thành Giai đoạn 1: SearXNG discovery-only

- Tách SearXNG khỏi `LiveProductSource`/`MultiSearchProvider` dùng cho pipeline xử lý trang sản phẩm. Adapter mới chỉ trả tiêu đề, URL, domain và nhãn `DISCOVERED`; không lấy snippet/ảnh làm dữ kiện, không tải trang ứng viên, không ghi Product/Offer.
- Kết quả được ghi trong `unified_sources` và snapshot hiện có; không thay schema database. Endpoint không đặt thì nguồn báo chưa cấu hình. Timeout, lỗi provider/HTTP và kết quả rỗng có test riêng; lỗi một phần giữ các URL thành công.
- Test mục tiêu: `backend/.venv/Scripts/python.exe -B -m pytest tests/unit/test_web_discovery_source.py tests/unit/test_multi_search_provider.py tests/integration/test_search_api.py tests/integration/test_candidate_discovery_api.py -q` — 25 passed, exit code 0.
- Backend regression: `.venv/Scripts/python.exe -B -m pytest -q --tb=short` trong `backend/` — 1084 passed, exit code 0. Có cập nhật các provider test double theo tham số mới để tiếp tục kiểm tra đường ingestion legacy.
- Smoke Live qua FastAPI dùng database SQLite tạm: HTTP 200, SearXNG trả 6 URL ứng viên cho truy vấn laptop; số Product và ProductOffer trước/sau bằng nhau. Tiến trình hoàn tất exit code 0. Không truy cập các URL ứng viên.
- `git diff --check` exit code 0; có thông báo chuẩn hóa LF/CRLF. Diff cuối đã rà trong các file thuộc thay đổi này; các thay đổi có sẵn khác trong working tree được giữ nguyên.
- Trạng thái: khám phá SearXNG `LIVE_VERIFIED`; giá, tồn kho, đánh giá và sản phẩm thương mại `LIVE_NOT_VERIFIED`. Backend runtime Compose mặc định vẫn chưa cấu hình endpoint, collector vẫn tắt, registry nguồn được duyệt vẫn rỗng.
- Chất lượng: `git diff --check` exit code 0. Ruff không cài trong virtualenv (`NOT RUN`); không tự cài dependency.

### 2026-10-29 — Hoàn thành Giai đoạn 2: trạng thái và cổng duyệt ứng viên

- Mỗi URL SearXNG giữ `status=DISCOVERED` và có `review_status` theo registry đã cấu hình: host chưa đăng ký/chờ duyệt → `REVIEW_REQUIRED`; quyền bị từ chối → `RESTRICTED`; được duyệt nhưng tắt → `DISABLED`; được duyệt và bật → `APPROVED`.
- `collector_eligible` chỉ true khi registration được duyệt và bật, hai cờ `collector_live_enabled`/`collector_policy_confirmed` cùng true, adapter hỗ trợ product page, URL dùng HTTPS trên port chuẩn và path nằm trong allowlist. Đây là kiểm tra tĩnh; collector vẫn tự kiểm tra URL, quyền, robots và preflight trước truy cập.
- Candidate status được đóng băng trong RecommendationSnapshot JSON hiện có, không thêm migration. Registry mặc định vẫn rỗng; chưa phê duyệt nguồn thương mại nào và không bật collector.
- Test mục tiêu: `.venv/Scripts/python.exe -B -m pytest tests/unit/test_web_discovery_source.py tests/unit/test_source_registry_preflight.py tests/unit/test_registered_collector_service.py tests/integration/test_search_api.py tests/integration/test_candidate_discovery_api.py -q --tb=short` trong `backend/` — 51 passed, exit code 0.
- Backend regression: `.venv/Scripts/python.exe -B -m pytest -q --tb=short` trong `backend/` — 1094 passed, exit code 0.
- Cập nhật [api.md](api.md) mô tả các trường trạng thái ứng viên và làm rõ SearXNG không chuyển URL vào product-page retrieval.

### 2026-10-29 — Đánh giá Open Food Facts / Open Products Facts

- Open Food Facts phù hợp riêng cho Research danh mục thực phẩm. Open Products Facts nhắm hàng phi thực phẩm nhưng tài liệu chính thức gọi API sibling là experimental; không thay thế nguồn Offer bán hàng.
- Đọc-only API smoke: Open Food Facts staging `coffee`, HTTP 200 JSON, tổng 15.995 kết quả; mẫu 5/5 có tên và ảnh. Open Products Facts production `laptop`, HTTP 200 JSON, tổng 11 kết quả; mẫu 5/5 có tên, 4/5 có ảnh. Barcode example chính thức chuyển tới OPF nhưng mẫu trả về không có tên sản phẩm. Không ghi dữ liệu vào database.
- Tài liệu API nêu dữ liệu đóng góp cộng đồng không đảm bảo đúng/đủ; có giới hạn request; cần custom User-Agent. OFF yêu cầu đọc điều khoản ODbL/DCL, giấy phép ảnh CC BY-SA và đề nghị điền API-usage form. OPF là experimental; cần xác minh điều khoản cụ thể của instance trước nhập/phân phối.
- Quyết định: chỉ cân nhắc như Research catalog với attribution, freshness và trạng thái không xác minh; tuyệt đối không tạo giá/Offer. Chưa nhập dữ liệu vì giấy phép/attribution và thông tin định danh API chưa được chốt. Giai đoạn 3/4 vẫn chờ điều kiện nguồn và không bật collector.
- Ma trận nguồn được cập nhật tại [CRAWLER_SOURCE_MATRIX.md](CRAWLER_SOURCE_MATRIX.md). Nguồn: [OFF API docs](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/) và [OPF experimental API docs](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/tutorials/scanning-cosmetics-pet-food-and-other-products/).
- Smoke Live qua FastAPI với SQLite tạm và registry rỗng: HTTP 200, 7 URL ứng viên, tất cả `REVIEW_REQUIRED`, không URL nào đủ điều kiện collector, số Product/Offer không đổi; exit code 0. Không mở URL kết quả.
- Giới hạn: duyệt/tắt nguồn thực hiện qua cấu hình registry theo runbook; chưa có admin UI/API. Giai đoạn 3 cần quyền và hồ sơ rà soát nguồn cụ thể.

### Mẫu checkpoint sau mỗi giai đoạn

```text
Ngày:
Giai đoạn:
Trạng thái trước → sau:
Thay đổi chính:
Lệnh kiểm tra và exit code:
Bằng chứng Live (nếu được phép):
Số lượng có mẫu số:
Lỗi/blocker còn lại:
Diff đã kiểm tra:
```
### 2026-10-29 — bounded Open Facts Research data

- The user approved a small Open Food Facts / Open Products Facts Research sample with
  license attribution and no current prices or Offers. This approval covers Research
  records only; it does not approve any merchant collector.
- Open Products Facts returned 11 records for one production `laptop` query (maximum
  25). The bounded importer added 11 Research products and 1 import run to local
  Compose PostgreSQL; total database counts are 242 products / 211 Research products /
  32 offers / 0 historical prices. Existing offers and schema were unchanged.
- Open Food Facts production returned HTTP 503 on its one query. No retry and no food
  import were performed. Earlier staging evidence is not production availability.
- Backend target tests: 11 passed; full backend regression: 1104 passed, exit 0.
  Frontend Research tests: 6 passed; complete frontend suite: 71 passed, exit 0;
  lint, type-check, and production build all exited 0. Two official OPF image HEAD
  checks returned HTTP 200 `image/jpeg`; Compose rebuild/start exited 0; the product
  detail API returned HTTP 200 with OPF attribution, image, and zero offers/ratings;
  Playwright opened `/products/232`, rendered Open Products Facts, ODbL/CC BY-SA and
  product name, with no page errors (exit 0). Frontend root returned HTTP 200.
  Commercial source discovery/crawl remains blocked pending a separately approved
  merchant source.
