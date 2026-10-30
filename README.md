# Smart Shopping AI

**XÂY DỰNG HỆ THỐNG TRỢ LÝ MUA HÀNG THÔNG MINH ỨNG DỤNG TRÍ TUỆ NHÂN TẠO**

Ứng dụng nhận nhu cầu mua hàng bằng tiếng Việt, tìm và chuẩn hóa sản phẩm, lọc theo yêu cầu, chấm điểm bằng Python và giải thích kết quả kèm nguồn. Đây là project đã phát triển các luồng MVP, không còn là skeleton PART 01.

Trang Home hiện chạy một luồng tìm kiếm hợp nhất: đọc catalog nội bộ và catalog nghiên cứu có nhãn lịch sử, đồng thời thử nguồn web đã được cấu hình. Nếu thiếu dữ liệu catalog và không có nguồn web khả dụng, hệ thống có thể trả 0 sản phẩm; nó không chèn sản phẩm fixture để lấp kết quả. API tìm kiếm chính không có công tắc Demo/Research/Live. `DEMO_MODE` là cờ cấu hình tương thích/runtime, không chứng minh sản phẩm trả về là dữ liệu giả hay dữ liệu Live.

## Tính năng

### Research Catalog — Mục tiêu A

Đã tích hợp Amazon Reviews 2023 **lịch sử**, không phải Live: SQLite local có
150 sản phẩm thật, 70 giá tham khảo USD, **0 ProductOffer tạo từ dataset**.
Catalog này được truy vấn bởi endpoint nghiên cứu riêng `/api/research/search`;
nó không phải một lựa chọn trên Home. Ví dụ: “phụ kiện điện thoại dưới 50 USD”, “điện tử”.
Ngân sách VND không so với USD; RAM/storage bắt buộc thiếu chứng cứ không được
coi là đạt. Không cần LLM/Tavily key, không fine-tune mô hình.

Phạm vi dữ liệu: nghiên cứu phi thương mại cục bộ, không tái phân phối raw/DB;
dataset không có giấy phép mở rõ ràng. [Đánh giá nguồn](docs/RESEARCH_DATA_SOURCE_ASSESSMENT.md),
[tiến độ R00–R09](docs/RESEARCH_DATA_PROGRESS.md),
[báo cáo và lệnh tái lập](docs/RESEARCH_DATA_INTEGRATION_REPORT.md).
R08 còn thiếu nhãn người đánh giá độc lập: Precision@K/NDCG hiện **N/A**.

Catalog bổ sung Amazon Berkeley Objects (ABO) dùng giấy phép [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
và hiện có tối đa 200 metadata sản phẩm trong PostgreSQL runtime local. Ảnh và thông số
chỉ có khi dataset cung cấp; ABO không có giá hiện hành, rating, review count, tồn kho
hoặc link mua hàng đã xác minh. Dữ liệu runtime/raw không được commit. Từ thư mục
`backend`, có thể tải lại mẫu bằng `python -m scripts.download_abo_research_sample`
và phần mở rộng bằng `python -m scripts.download_abo_research_extension`; importer
mặc định dry-run và chỉ ghi database khi truyền `--apply`. Để nhập đủ mẫu đã duyệt,
chạy dry-run trước cho từng phần. Phần mở rộng:

```powershell
python -m scripts.import_abo_research_sample --input data/research/abo-extension-64/abo-extension-64.jsonl --images data/research/abo/images.csv.gz --manifest data/research/abo-extension-64/manifest.json --limit 64
```

Chỉ thêm `--apply` sau khi đã xem báo cáo dry-run.

`HISTORICAL_RESEARCH` không phải offer hiện hành. `LIVE` chỉ mô tả lần thử truy
cập nguồn hiện tại, **không tự động đồng nghĩa LIVE_VERIFIED**. Mock fixtures chỉ
dành cho test/compatibility, không được coi là offer mua hàng. Research không
bật collector flags hoặc giải quyết thay blocker quyền truy cập crawler.

| Thành phần | Implementation hiện tại |
|---|---|
| Requirement Analyzer / Clarification | Trích category, budget, purpose, brands, tiêu chí/ưu tiên; hỏi bổ sung khi thiếu dữ liệu. Demo parser local; Live thử LLM rồi fallback local. |
| Query Generator | Python tạo query mua hàng từ requirement/source strategy, không gọi LLM. |
| Search Provider | Unified search dùng Tavily và/hoặc SearXNG do operator cấu hình; không tự bật public SearXNG hay fallback sang mock. Mock providers chỉ dùng trong test/compatibility. |
| Extraction / Normalization | Parser deterministic từ search payload; chuẩn hóa tên, category theo evidence, giá VND, rating, review count, specifications. |
| Deduplication / Product / Product Offer | Hợp nhất Product; mỗi merchant/source có offer riêng. Không copy category từ yêu cầu sang sản phẩm. |
| Hard Filter / Scoring / Ranking | Lọc category, budget, brand, exclusion; Python tính 6 điểm thành phần và Top K. Không tạo dữ liệu để đủ K. |
| Structured Requirement Matching | matched / unmet / unknown, requested value, product value, reason. Thiếu dữ liệu không đồng nghĩa đáp ứng hoặc vi phạm. |
| Structured Evidence | Nguồn từng price/rating/review/specification phải được observation của session hỗ trợ. Thiếu nguồn để rỗng. |
| Recommendation Snapshot | Lưu giá, thông số, score, matching, evidence, explanation cùng thời điểm; session cũ không ghép giá mới vào score cũ. |
| AI Explanation | Demo deterministic; Live OpenAI/Gemini với timeout/retry/fallback. LLM không quyết định numerical score. |
| Product detail / Comparison | Detail đọc catalog hiện có. Comparison mới dùng snapshot/legacy view nhất quán; kết luận do Python, không gọi LLM. |
| Feedback / History | Ghi phản hồi và xem lại phiên. History dùng chung database local, chưa có đăng nhập/phân quyền. |
| Cache | The legacy `CachedSearchService` has a SQLite cache (TTL 1800s); Home unified search does not reuse cross-session cache and checks configured sources on each run. |
| Frontend / Browser E2E | Home automatic search, summary, score breakdown, matching/evidence, filter/sort, compare, feedback, history; Playwright dùng database cô lập và nguồn giả lập trong test, không phải Live acceptance. |
| Marketplace upgrade | Contract typed cho collector, URL Shopee/Lazada trực tiếp, ProductVariant + Offer + PriceObservation, score Product/Offer hai cấp, freshness và cảnh báo so giá khác SKU. Live collector mặc định khóa theo policy. |

AI Match là điểm phù hợp theo quy tắc, không phải xác suất mua đúng. Data Confidence là chỉ số chất lượng/độ đầy đủ dữ liệu riêng, chưa được hiệu chuẩn thống kê. Voice là **NOT REQUIRED FOR MVP**. Xem [final audit](docs/FINAL_AUDIT.md).

## Kiến trúc và stack

```mermaid
flowchart LR
  U[Người dùng] --> F[Next.js]
  F --> A[FastAPI]
  A --> R[Requirement / Clarification]
  R --> S[Query / Search / Extraction]
  S --> N[Normalize / Dedup / Hard Filter]
  N --> P[Python Score / Rank / Evidence]
  P --> E[Explanation]
  E --> D[(Snapshot / History)]
  D --> F
```

- Frontend: Next.js **16.4.1**, React **19.2.8**, TypeScript, Tailwind CSS 4.
- Backend: Python, FastAPI, Pydantic 2, SQLAlchemy 2; SQLite WAL locally and PostgreSQL 17 in Docker Compose.
- Adapters: OpenAI qua HTTP, Gemini qua `google-genai`, Tavily and operator-managed SearXNG over HTTP.
- Tests: pytest, Node test runner/React render, ESLint, Playwright **1.63.0**.
- Toolchains observed in this workspace: backend tests on Python **3.12.0**, local frontend on Node **24.19.0**, and Playwright **1.63.0**; Docker images use Python **3.13** and Node **22**. Node 22.6+ supports `--experimental-strip-types` for frontend tests.
- Frontend cài bằng lockfile `npm ci`. Backend giữ dependency ranges trong `requirements.txt`, chưa có Python lockfile; lần cài mới có thể nhận patch khác.

## Cấu trúc thực tế

```text
backend/
  app/
    api/routes/       # health, requirements, search, recommendations,
                      # products, comparison, feedback, history
    core/             # config, database, constants
    models/           # 14 bảng SQLAlchemy
    schemas/          # request/response, ranking, matching, evidence
    services/         # llm, search, extraction, normalization, dedup, filter,
                      # scoring, recommendation, validation, cache
    repositories/     # namespace dự phòng; ORM hiện nằm ở route/service
    main.py
  scripts/run_e2e_backend.py
  tests/              # conftest, unit, integration
  requirements.txt  .env.example  Dockerfile
frontend/
  app/                # /, /results/[sessionId], /products/[productId],
                      # /compare/[comparisonId], /history
  components/  lib/  types/  tests/  e2e/
  playwright.config.ts  package.json  package-lock.json  Dockerfile
docs/
.env.example  .dockerignore  docker-compose.yml
```

## Chạy local trên Windows PowerShell

Sau khi clone, mở terminal tại thư mục chứa README này. Không cần activate venv khi gọi trực tiếp Python trong `.venv`.

**Terminal 1 — backend:**

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Lệnh copy dành cho clone mới, không ghi đè `.env` đã cấu hình. Giữ `DEMO_MODE=true`, API keys rỗng. Startup tự tạo các bảng còn thiếu; không cần tự gọi `init_db()`. URL mặc định tạo `backend/smart_shopping.db`.

Kiểm tra [health](http://127.0.0.1:8000/api/health), [database/Demo status](http://127.0.0.1:8000/api/system/status), [Swagger](http://127.0.0.1:8000/docs).

**Terminal 2 — frontend:**

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Mở [http://localhost:3000](http://localhost:3000). Browser mặc định gọi `http://127.0.0.1:8000`. Backend cho phép hai origin `localhost:3000` và `127.0.0.1:3000`. Dừng server bằng Ctrl+C.

Frontend production local: chạy `npm.cmd run build`, sau đó `npm.cmd start` từ `frontend/`.

## Environment và Live Mode

| File | Được đọc bởi |
|---|---|
| `backend/.env` | Pydantic khi chạy backend từ `backend/`. Process environment ưu tiên hơn file; restart sau khi đổi. |
| `.env` ở root | Docker Compose interpolation; không tự được backend local đọc khi cwd là `backend/`. |
| `frontend/.env.local` | Next.js; chỉ đặt cấu hình công khai như `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`. |

Hai `.env.example` không có secret, liệt kê đầy đủ Settings hiện tại. `NEXT_PUBLIC_API_URL` là URL browser truy cập, được nhúng lúc build; đổi nó cần build lại. Không dùng `http://backend:8000` cho browser trên host. [Tài liệu Next.js](https://nextjs.org/docs/app/guides/environment-variables#bundling-environment-variables-for-the-browser).

| Biến backend | Mặc định |
|---|---|
| `APP_ENV` / `DATABASE_URL` | `development` / `sqlite:///./smart_shopping.db` (local default; Docker Compose uses PostgreSQL 17) |
| `DEMO_MODE` | `true` |
| `LLM_PROVIDER` / `LLM_FALLBACK_PROVIDER` | `openai` / `gemini` |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `TAVILY_API_KEY` | Rỗng |
| `OPENAI_MODEL` / `GEMINI_MODEL` | `gpt-4o-mini` / `gemini-3.6-flash` (chuỗi mặc định trong config; chưa xác minh quyền truy cập model Live) |
| `LLM_TIMEOUT_SECONDS` / `SEARCH_TIMEOUT_SECONDS` | 30 / 15 |
| `LLM_RETRY_COUNT` / `SEARCH_RETRY_COUNT` | 2 / 1 |
| `MAX_SEARCH_QUERIES` / `MAX_RESULTS_PER_QUERY` / `TOP_K` | 4 / 5 / 5 |
| `CACHE_TTL_SECONDS` | 1800; không dương thì vô hiệu hóa cache |
| `PRODUCT_OFFER_FRESHNESS_TTL_SECONDS` | 3600; độc lập với search-result cache |
| `COLLECTOR_MAX_URLS` | 5 URL trực tiếp mỗi request |
| `COLLECTOR_LIVE_ENABLED` / `COLLECTOR_POLICY_CONFIRMED` | `false` / `false`; cả hai chỉ bật khi operator có quyền phù hợp |
| `ENABLE_LLM_EXTRACTION_FALLBACK` | `false`; fallback chỉ nhận specs, không nhận giá/ID/rating/stock |
| `SECRET_KEY` | Placeholder `change-this-before-production`, chưa dùng làm authentication trong MVP |

Unified web search chỉ gọi Tavily khi có key hoặc SearXNG khi operator cấu hình endpoint; cấu hình provider model/key riêng nếu muốn dùng LLM cho analyzer/explanation. Chọn model khả dụng trong tài khoản; không coi giá trị mặc định là bảo đảm provider đang cung cấp model đó. Khi thiếu nguồn web hoặc nguồn lỗi, search báo trạng thái và giữ dữ liệu hợp lệ khác; không âm thầm biến mock thành Live. Tests không gọi API trả phí. `DEMO_MODE=false` không cấp quyền truy cập nguồn bên ngoài.

Collector marketplace là một opt-in riêng với Live search. Điều khoản công khai được rà
soát ngày 2026-10-15 không cung cấp bằng chứng quyền crawl cho repository này, vì vậy
Shopee/Lazada đang ở trạng thái `ACCESS_RESTRICTED`; xem [collector policy](docs/collector-policy.md).
Không bật hai cờ collector nếu chưa có thẩm quyền/đồng ý áp dụng.

Collector nguồn storefront công khai cũng mặc định fail-closed: registry rỗng, chưa có
merchant điện tử nào được duyệt hoặc xác minh Live. WooCommerce Store API và HTTPX/JSON-LD
được kiểm thử offline; xem [crawler runbook](docs/CRAWLER_RUNBOOK.md),
[đánh giá](docs/CRAWLER_EVALUATION.md), [source matrix](docs/CRAWLER_SOURCE_MATRIX.md)
và [tiến độ](docs/CRAWLER_PROGRESS.md). DNS/IP được kiểm tra lại và ghim tại lúc
mở kết nối; registry vẫn fail-closed và không được bật merchant chưa có căn cứ quyền.

Benchmark offline tái lập:

```powershell
cd backend
.\.venv\Scripts\python.exe -B -X utf8 -m benchmarks.run --output ..\docs\benchmark-results
```

Kết quả này là `FIXTURE_TESTED_ONLY`, không phải Live.

Sau khi đã cấu hình một nguồn được phép trong
`COLLECTOR_SOURCE_REGISTRY_JSON` và bật cả hai cờ policy, có thể nạp trước
catalog điện thoại, laptop/máy tính để bàn và tai nghe vào database hiện tại:

```powershell
cd backend
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.ingest_catalog
```

Job này không fine-tune mô hình; nó chuẩn hóa và upsert dữ liệu có bằng chứng
vào chính các bảng mà recommendation đang đọc. Registry rỗng hoặc nguồn bị
chặn sẽ trả lỗi và không tạo dữ liệu giả. Xem tùy chọn `--query`, `--url` và
quy trình phê duyệt nguồn trong [crawler runbook](docs/CRAWLER_RUNBOOK.md).

Với thao tác Live thủ công, ưu tiên CLI có preflight và hard cap:

```powershell
cd backend
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.crawl_products preflight --url "https://APPROVED-HOST/product/example"
.\.venv\Scripts\python.exe -B -X utf8 -m scripts.crawl_products ingest --live --max-products 5 --max-pages 2
```

Crawl4AI là dependency tùy chọn trong `backend/requirements-browser.txt`; xem
runbook trước khi bật `COLLECTOR_BROWSER_ENABLED`.

## Validation

Từ `backend/`:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m pytest
```

Từ `frontend/`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
```

Pytest tự dùng database tạm sạch. Playwright tự khởi động backend **18000** và frontend **13000** với database tạm, catalog tổng hợp và network guard; không dùng DB thật hoặc chứng minh Live retrieval. Edge được ưu tiên nếu đã cài; nếu không có, cài Chromium bằng `npx.cmd playwright install chromium`. Không chạy E2E cùng Next dev/build khác trong cùng thư mục. Sau E2E, build lại trước `npm start` bình thường vì `.next` đã nhúng URL test. Chi tiết: [testing](docs/testing.md).

## Docker local

Yêu cầu Docker Engine/Desktop chạy Linux containers và Docker Compose v2. Config, image build và runtime đã kiểm tra ngày 2026-10-29 bằng Compose project cùng PostgreSQL volume cô lập; lệnh `up` mặc định vẫn tạo volume bền `shopping-data` để giữ dữ liệu local.

Tại root, dùng example với provider keys rỗng để kiểm tra cấu hình/build local:

```powershell
docker compose --env-file .env.example config
docker compose --env-file .env.example build
docker compose --env-file .env.example up -d
Invoke-RestMethod http://127.0.0.1:8000/api/system/status
Invoke-WebRequest http://127.0.0.1:3000 -UseBasicParsing
docker compose --env-file .env.example logs --tail 50
docker compose --env-file .env.example down
```

Mở frontend và thử một [scenario](docs/demo.md). Có thể gộp build/start bằng `docker compose --env-file .env.example up --build -d`. Backend healthcheck dùng database status; frontend chờ backend healthy. Port chỉ publish lên loopback local. Named volume `shopping-data` chứa `/data/smart_shopping.db`; `down` giữ volume. Không bind-mount DB thật và không dùng `down -v` nếu cần giữ dữ liệu.

`.dockerignore` loại env/secrets, database, venv, node_modules, build output và artifacts. Keys chỉ truyền runtime vào backend. Image frontend giữ toolchain Next/TypeScript cho config hiện tại, chưa tối ưu kích thước. Đây là Docker local MVP, không phải public deployment.

SearXNG is optional and is not started by the default Compose profile. To run
the pinned local service, publish it only on loopback, and enable JSON (needed
by the adapter), use a generated local secret and set the backend URL in the
same PowerShell session:

```powershell
$env:SEARXNG_SECRET = (New-Guid).Guid.Replace('-', '')
$env:SEARXNG_BASE_URL = "http://searxng:8080"
docker compose --env-file .env.example --profile searxng up -d searxng
```

For the backend container to use it, start the normal app services in that
same session with `docker compose --env-file .env.example --profile searxng
up --build -d`; the `SEARXNG_BASE_URL` value is passed to the backend. To test
only the local search service from the host, set the URL to
`http://127.0.0.1:8080`. SearXNG sends search
queries to the search engines configured in its upstream defaults; review their
policies for your use. Search results are discovery evidence only, not verified
prices, inventory, or ratings. Keep marketplace collectors disabled unless
their source permissions are established.

## Troubleshooting

| Vấn đề | Cách xử lý |
|---|---|
| PowerShell chặn Activate.ps1/npm.ps1 | Dùng đường dẫn Python `.venv` và `npm.cmd`; không cần đổi execution policy toàn máy. |
| No module named / sai Python | Kiểm tra `where.exe python`; cài qua chính `.venv\Scripts\python.exe -m pip`. |
| Node không hiểu strip-types | Dùng Node 22.6+ (đã test 22.21.1), rồi `npm.cmd ci`. |
| Không có bảng / không mở SQLite | Chạy đúng cwd; startup tạo schema. Parent directory của URL tùy chỉnh phải tồn tại và có quyền ghi. Không xóa DB để chữa lỗi. |
| Database locked | Dừng instance dư ghi cùng DB; WAL/busy timeout đã bật. Tests có DB riêng. |
| Port conflict | Dừng đúng server giữ 8000/3000 hoặc 18000/13000. E2E không reuse server có sẵn. Đổi port frontend còn cần CORS phù hợp. |
| Failed to fetch | Kiểm tra health, API URL của browser, origin 3000; build lại nếu đổi public URL/vừa chạy E2E. |
| Key thiếu/model lỗi | Demo dùng keys rỗng; Live cần đúng provider/model/key và restart. |
| Không có đề xuất | Xem warnings/filter decisions. Top K là tối đa, không tự bịa thêm sản phẩm. |
| Playwright không có Edge | Kiểm tra path Edge Windows; máy khác cài Chromium bằng lệnh trên. |
| E2E kẹt teardown trong sandbox | Chạy terminal local cho phép tạo/dừng process con, không thay bằng server/DB thật. |
| Pytest cache permission warning | Test DB vẫn tách biệt; sửa quyền cache hoặc dùng `-o cache_dir=<thư_mục_có_quyền_ghi>`. |
| Docker không khả dụng | Cài/bật Docker riêng rồi validation; pytest không chứng minh image chạy được. |

## Tài liệu

[Architecture](docs/architecture.md) · [Database](docs/database.md) · [API](docs/api.md) · [Testing](docs/testing.md) · [Crawler runbook](docs/CRAWLER_RUNBOOK.md) · [Crawler evaluation](docs/CRAWLER_EVALUATION.md) · [Demo](docs/demo.md) · [Presentation](docs/presentation.md) · [MASTER_SPEC](docs/MASTER_SPEC.md) · [Final audit](docs/FINAL_AUDIT.md)
