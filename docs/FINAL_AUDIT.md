# FINAL AUDIT — Phase 7

Ngày kiểm tra: 2026-09-14. Phạm vi: project hiện hữu, PROJECT OVERRIDES ưu tiên
specification gốc; tiếp tục Phase 7, giữ Phase 1–6. Không commit/reset Git, không
đọc/chỉnh secret trong `.env`, không dùng/backfill/xóa database thật.

**Kết quả xác nhận local/Demo: CRITICAL = 0, HIGH = 0 còn mở.** Đây là kết luận
trong phạm vi code và kiểm thử bên dưới, không chứng nhận production/security
hay khả năng cung cấp của API Live. Docker **PARTIAL — NOT RUNTIME VERIFIED**.
Các mục chưa đủ specification được ghi rõ, không đổi nhãn thành PASS để đạt đích.

## Thay đổi Phase 7

| File sửa/tạo | Nội dung |
|---|---|
| `backend/app/api/routes/comparison.py` | Comparison dùng RecommendationService.load: cùng snapshot hoặc complete legacy view, thay vì trộn catalog/offer mới với score cũ |
| `backend/tests/integration/test_comparison_api.py` | Thêm 2 regression: cập nhật giá/rating/spec catalog sau snapshot; legacy tính lại chỉ đọc, không backfill |
| `backend/tests/integration/test_demo_scenarios.py` (mới) | 3 scenario Demo, analysis đến search/detail/compare/feedback/History; in số liệu thật cho tài liệu |
| `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore` (mới) | Images local MVP, process non-root, backend healthcheck, loại env/DB/dependencies/artifacts khỏi context |
| `docker-compose.yml` | Hai services, loopback ports, health dependency, SQLite named volume, browser public URL lúc build |
| `.env.example`, `backend/.env.example` | Đủ 19 Settings thực tế, keys rỗng; root thêm NEXT_PUBLIC_API_URL cho Compose |
| `README.md` | Setup Windows, kiến trúc/chức năng, env local/Compose, Demo/Live, tests/E2E/Docker/troubleshooting |
| `docs/architecture.md` | Luồng thực, AI/Python, scoring, snapshot/cache/History và giới hạn |
| `docs/database.md` | 14 bảng, quan hệ, snapshot JSON, local/test/Docker DB, không migration/backfill |
| `docs/api.md` | 16 application endpoints, validation/errors, response và semantics tương thích |
| `docs/testing.md` | Lệnh chạy, regression map, temp DB/mocks, browser suite và Docker chưa runtime |
| `docs/demo.md` | 3 scenario với giá/score/status từ test, quy trình 15 bước |
| `docs/presentation.md` | Đề cương 12–15 phút, 15 câu hỏi bảo vệ và file chứng minh |
| `docs/FINAL_AUDIT.md` (mới) | Báo cáo này |

Tổng **17 file**: 12 sửa, 5 tạo. Không sửa frontend source/UI, dependency/lockfile,
routes, scoring weights, models hay SQL schema trong Phase 7.

## HIGH comparison đã xử lý

Root cause: serializer cũ lấy Product/Offer đang thay đổi trong catalog, nhưng lấy
score/rank/confidence từ recommendation lịch sử. Sau một search khác cập nhật offer,
comparison có thể hiển thị giá mới với điểm tính từ giá cũ.

Serializer mới nhận `RecommendationItem` từ view thống nhất. Với session có snapshot,
price/rating/specification/score và narrative cùng snapshot. Với legacy không có
snapshot, tái sử dụng phép tính lại đầy đủ, chỉ đọc của Phase 3. Pros/cons lấy
why_fit/tradeoffs của cùng view; winner vẫn deterministic theo score/rating/reviews.
GET comparison đọc JSON result đã lưu.

Không đổi SQL schema. `result.data_semantics` là field bổ sung trong JSON response
hiện có (`snapshot`/`legacy_recomputed`); payload cũ thiếu field vẫn đọc được.
Không đổi API route/request. Comparison đã lưu trước fix không được viết lại hoặc
đoán lại dữ liệu lịch sử đã thiếu; giới hạn này được giữ rõ trong mục còn lại.

Regression đầu đã tái hiện thất bại trước fix (giá snapshot 449000 bị thay bằng
20000000). Sau fix, test kiểm tra cả price/rating/specification/score, GET comparison
và snapshot không đổi. Test thứ hai xác nhận legacy recompute, không tạo snapshot
và không sửa score rows đã lưu. Suite comparison cuối: **10/10 PASS**.

## Ma trận MASTER_SPEC

Nhãn theo yêu cầu FINAL PHASE 7: **PASS**, **PARTIAL**, **MISSING**,
**NOT REQUIRED FOR MVP**. PASS nghĩa chức năng hiện tại đạt phần được mô tả và kiểm
thử, không có nghĩa mọi ngôn ngữ/website/dataset đều được hỗ trợ. Các khác biệt tên
file/route/schema tương đương được chấp nhận theo PROJECT OVERRIDES.

| Chức năng / mục SPEC | Trạng thái | Bằng chứng / khác biệt / ưu tiên còn lại |
|---|---|---|
| Mục tiêu local, luồng end-to-end (I, LIX, LXIII) | PASS | Home → analysis → search → recommendation → comparison/feedback/History; browser Demo thực |
| LLM/Python separation, orchestrator (II, III, V, LVII) | PASS | Routes + services orchestration; final score/ID/giá không do LLM quyết định; không cần đổi tên thành shopping_pipeline |
| Next/TS/Tailwind, FastAPI/Pydantic/SQLAlchemy/SQLite (IV) | PASS | Stack giữ nguyên; backend và frontend chạy trong E2E |
| Gemini/OpenAI structured clients (IV, VII, XLVIII) | PASS | Provider/config có thật, structured schema, mock tests; OpenAI mặc định và Gemini fallback là config hiện hữu hợp lệ |
| Live end-to-end thực (I, IV, XLVIII) | PARTIAL | Có clients thật và mock timeout/error tests; không gọi API thật để xác minh key/model/nguồn trong đợt này; MEDIUM validation gap |
| Cấu trúc project (VI, LVII) | PASS | Module chức năng có thật; ORM hiện trong route/service, repositories namespace dự phòng; không refactor theo cây mẫu |
| Requirement analysis (VII) | PASS | Category, budgets, purpose, brands, requirements/priorities, exclusions, confidence; analyzer unit/integration tests |
| Clarification (VIII) | PASS | Nhận diện thiếu thông tin, lưu session, tiếp nhận câu trả lời trước search |
| Query generator (IX) | PARTIAL | Sinh query giới hạn bởi config, unit tests PASS; Python template, chưa LLM-generated như câu chữ gốc; MEDIUM |
| Search abstraction/Tavily/source filter (X, XI) | PASS | Provider riêng, source domain/URL/reliability, skip source/query lỗi; không có cơ chế bypass access controls |
| Product extraction (III, XII) | PARTIAL | Parser deterministic cho labelled payload và một số mẫu search text; chưa LLM extraction tổng quát/đa website; MEDIUM |
| Product/Offer/source schema (XII, XXX, XXXI) | PASS | Product và offers tách riêng; merchant/price/URL/timestamp theo nguồn |
| Structured evidence (XIII, XLIII) | PASS | Field/value/source/domain/merchant/url/retrieved_at/reliability; chỉ attribution khi observation tương ứng; thiếu nguồn để rỗng |
| Price parser (XIV) | PASS | VND/k/triệu, dấu ngăn cách; unit tests |
| Rating/review count parser (XIV và overrides) | PASS | Chuẩn hóa giá trị và missing; tests riêng |
| Text/product/category normalization (XIV) | PASS | Category từ evidence product; laptop request không biến headphone thành laptop |
| Deduplication/Product Offer (XV) | PARTIAL | Exact normalized brand+model hoặc normalized name, category guard; nhiều offers đúng. Chưa fuzzy similarity như SPEC gợi ý; MEDIUM |
| Hard filter (XVI) | PASS | Category/budget/brand/exclusions/availability, weight kg/g; unit + category integration |
| Missing data / structured matches (XVII) | PASS | Mỗi explicit requirement: name/requested_value/product_value/status/reason; missing/uncomparable=unknown, observed failure=unmet |
| Budget scoring (XVIII) | PASS | Python deterministic, đúng budget/hard-filter regression |
| Requirement value scoring (XVIII) | PASS | Kiểm tra value/units, RAM 8GB không thỏa 16GB; unknown không cộng điểm; không requirement thì mặc định 100 và matching rỗng |
| Purpose scoring (XVIII) | PASS | Heuristic Python theo evidence/aliases; không phải benchmark/calibration thực nghiệm |
| Rating/review scoring (XVIII) | PASS | Component deterministic, xử lý thiếu dữ liệu; tests |
| Source scoring/constants (XX) | PASS | Tập trung 100/90/80/70/50 trong core/constants.py |
| Final score/breakdown (XVIII, XIX) | PASS | 25/30/20/10/5/10 giữ nguyên; API thành phần 0–100, UI điểm gốc + trọng số, khác shape contribution minh họa nhưng tương đương |
| Data Confidence (XXI) | PARTIAL | Tách AI Match, có quality/completeness/consistency/corroboration; chưa freshness decay riêng; MEDIUM |
| Ranking/Top K (XXII) | PASS | TOP_K mặc định 5, không bịa đủ số lượng; 3 Demo hợp lệ trả 3 |
| AI explanation (XXIII) | PASS | demo/openai/gemini/fallback; timeout/retry và fallback an toàn; LLM không ghi đè numeric fields; Live mock integration |
| Comparison (XXIV) | PARTIAL | Chức năng 2–3 sản phẩm, bảng/narrative/winner và snapshot consistency PASS; kết luận Python, chưa LLM comparison riêng như SPEC gốc; MEDIUM |
| API contract (XXV, XXVI) | PASS | Giữ /api/comparisons và dynamic routes theo overrides; snapshot/counts/warnings rõ; docs/api.md |
| DB/session/requirement/recommendation (XXVII–XXXII) | PASS | 10 bảng yêu cầu cùng 4 bảng hỗ trợ; statuses PENDING/PROCESSING/COMPLETED/FAILED |
| Snapshot consistency (overrides; Phase 3/6) | PASS | Session A không trộn giá B; count cùng run; evidence/matches được lưu JSON; legacy read-only semantics |
| Cache (XXXIII) | PASS | Database abstraction, normalized key + config, TTL 1800, copy snapshot; không đổi semantics Phase 4 |
| Fallback (XXXIV, LXI) | PASS | LLM fallback local; search retry/cache theo điều kiện; lỗi hết giữ kết quả cũ và warnings; Demo bật chủ động |
| Retry/timeout (XXXV) | PASS | Defaults LLM 30s/2 retries, search 15s/1 retry; giới hạn hữu hạn, tests mocked |
| Logging hiện tại (XXXVI) | PARTIAL | Có provider/route warnings/errors và processing time; chưa đầy đủ per-request/stage telemetry; MEDIUM |
| Request ID + correlated stage latency logging (XXXVI) | MISSING | Chưa có middleware tracing đầy đủ mọi request; MEDIUM, không thêm trong phase này |
| Secrets/input limits/URL safety (XXXVII) | PASS | Keys ở backend env; .env.example rỗng keys, input/schema giới hạn; UI chỉ link HTTP(S), text escaping tests; không là full security audit |
| Home/presets (XXXVIII) | PARTIAL | Input, submit, 3 presets chính; chưa đủ 6 presets trong ví dụ; LOW |
| Filter/sort UI (XXXIX) | PASS | Category/budget/brand; AI Match/price/rating; frontend unit và browser tests, không đổi backend scores |
| Loading/progress (XL) | PARTIAL | Có trạng thái analysis/search; chưa telemetry realtime toàn bộ extraction/normalize/score/rank; MEDIUM |
| Product card/detail (XLI) | PASS | Giá, thông tin có sẵn, scores/confidence, detail/compare/explanation; thiếu metadata không bịa; catalog detail là current view |
| Score breakdown UI (XLII) | PASS | Component scores + đúng trọng số; frontend tests |
| Match/evidence UI (XLIII + Phase 6) | PASS | Backend matched/unmet/unknown, value/reason/source/time; frontend không suy diễn, safe links, legacy empty |
| History UI/API (XLIV) | PASS | List + xem lại snapshot/session/warnings, không gọi provider, không đổi semantics |
| Comparison UI (XLV) | PASS | Dynamic route đang dùng, 2–3 products, table/winner; E2E |
| Feedback (XLVI) | PASS | Hữu ích/không phù hợp, reason/comment lưu DB; chưa dùng để học mô hình |
| Voice (XLVII) | NOT REQUIRED FOR MVP | Future Work; không làm dependency bắt buộc |
| Demo Mode (XLVIII) | PASS | Offline không key, 3 scenario thực; phân biệt persisted data_mode và runtime mode |
| Unit/integration/browser tests (XLIX, L) | PASS | 254 backend + 19 frontend + 3 browser, sạch DB/mocks, không test bị xóa/làm yếu |
| Documentation (LI) | PASS | README và 6 tài liệu yêu cầu hoàn thiện, bổ sung FINAL_AUDIT |
| Environment examples (LII) | PASS | Static assertions: 19/19 backend Settings đúng defaults, keys rỗng; public frontend URL riêng |
| Implementation/config/services (LIII, LIV) | PARTIAL | Core code thật, type/schema validation và providers; còn duplicate helpers, namespace dự phòng và logging chưa đủ; LOW/MEDIUM đã ghi |
| Docker local (LXV PART 11 / yêu cầu Phase 7) | PARTIAL | Static YAML/config PASS; không có Docker CLI/runtime: NOT RUNTIME VERIFIED; MEDIUM |
| Demo scenarios (LX) | PARTIAL | 3 scenario của Phase 7 PASS 3/3/3; không bịa 5 products. Chưa claim toàn bộ câu mở rộng “không muốn máy quá nặng” và từng stage hiển thị như ví dụ gốc; MEDIUM |
| Presentation (LXII) | PASS | 15 câu hỏi, câu trả lời đúng implementation, run-of-show và giới hạn |
| Workflow/checkpoints/overrides (LV, LVI, LVIII, LXIV–LXVI) | PASS | Tiếp tục project cũ, diff trước sửa, bounded fix và kiểm thử; tên phase gốc dùng để audit, không dựng lại hay chuyển phase mới |
| PostgreSQL/Redis/public deployment | NOT REQUIRED FOR MVP | SQLite local/database cache là MVP; cần validation/vận hành riêng nếu mở rộng |
| Personalization/price tracking/notifications/vector/hybrid/feedback learning/multi-agent (LXII) | NOT REQUIRED FOR MVP | Future Work, chưa triển khai |

Không phát hiện xung đột còn mở cần đổi API/stack/schema. Các khác biệt substantive
với câu chữ gốc vẫn là PARTIAL/MISSING trong bảng, không bị bỏ qua bằng overrides.

## Final validation thực tế

Chạy Windows, Python 3.13.12, Node 22.21.1, Next 16.3.3, Edge headless/Playwright.
Các lệnh backend từ `backend/`, npm từ `frontend/`. Backend dùng `.venv` nằm trong
backend. Không chạy pytest bằng database ứng dụng.

| Kiểm tra | Collected / pass / fail | Kết quả / warnings |
|---|---|---|
| `.\.venv\Scripts\python.exe -B -X utf8 -m pytest` | **254 / 254 / 0** | PASS, **2 warnings**, 8.27s |
| Comparison riêng: `pytest tests/integration/test_comparison_api.py -v` với cùng Python flags | **10 / 10 / 0** | PASS, **2 warnings**, 1.01s |
| Demo riêng: `pytest tests/integration/test_demo_scenarios.py -v -s` với cùng Python flags | **3 / 3 / 0** | PASS, **2 warnings**, 0.73s |
| `npm.cmd test` | **19 / 19 / 0** | PASS, không skip/cancel; 1 Node module-type warning |
| `npm.cmd run lint` | 0 errors | PASS exit 0, **2 warnings** hiện hữu |
| `npm.cmd run test:e2e` | **3 / 3 / 0** | PASS, 21.9s, 1 worker, không retry/skip; Node color-env warnings |
| `npm.cmd run build` sau E2E | — | PASS exit 0, compile/TypeScript/page generation thành công, giữ nguyên các routes |
| Docker/env static assertions | — | PASS phạm vi tĩnh; **NOT RUNTIME VERIFIED** |

Hai pytest warnings: Starlette TestClient deprecates `httpx`; pytest không có quyền
ghi `.pytest_cache/v/cache/nodeids` trong sandbox Windows. Không ảnh hưởng schema
test tạm hoặc assertions, không nâng dependency để che warning.

Frontend unit warning: `MODULE_TYPELESS_PACKAGE_JSON` khi Node đọc TS module.
ESLint warnings hiện hữu: useMemo dependency `products` ở compare page và internal
navigation qua `window.location.href` ở Home. Browser logs cảnh báo `NO_COLOR` bị
`FORCE_COLOR` ghi đè; không phải browser failure.

Pytest conftest đặt DATABASE_URL tạm trước collection, kiểm tra engine path, tạo/drop
schema mỗi test và cleanup. E2E launcher dùng SQLite tạm riêng, Demo=true, keys rỗng,
network guard; browser chỉ truy cập local 13000/18000. Chạy E2E với quyền tạo/dừng
process con để teardown Windows hoàn tất. Build bình thường đã chạy lại sau E2E
để `.next` không còn bundle URL test. Không có cuộc gọi paid API trong tests.

## Regression Phase 1–6

| Phase | Kết quả |
|---|---|
| 1 | PASS: database isolation, all-provider failure giữ recommendations/snapshot, FAILED và warnings tồn tại khi GET |
| 2 | PASS: category evidence/filter, requirement value scoring, kg/g với dấu thập phân, analyzer và budget/range VND |
| 3 | PASS: snapshot không ghép catalog mới, counts nhất quán, mocked Live explanation modes/timeout/fallback |
| 4 | PASS: History và cache hit/miss/expiry/failure, snapshot copy, không thay cache/History semantics |
| 5 | PASS: result metadata, filter/sort, breakdown, Demo provenance, frontend tests/lint/build |
| 6 | PASS: structured matches/evidence, historical metadata/cache compatibility, UI render và 3 browser scenarios |

249 backend tests có sẵn được giữ; thêm 2 comparison + 3 parameterized Demo = 254.
Browser scenario 1 là Demo thực trọn hành trình; scenario 2 là response fixture ba
match states/evidence/safe links; scenario 3 là historical metadata thiếu + warning
search failure. Không trình bày cả ba như Live test hoặc ba Demo category browser.

## Số liệu Demo đã xác minh

| Scenario | Budget max | Found / qua lọc / recommended | Top 1 | Giá VND | Score |
|---|---:|---|---|---:|---:|
| Tai nghe học online | 500000 | 3 / 3 / 3 | SoundDemo H20 Wireless | 449000 | 92.44 |
| Laptop học lập trình | 15000000 | 3 / 3 / 3 | CodeBook 15 | 14490000 | 92.45 |
| Điện thoại camera/game | 5000000 | 3 / 3 / 3 | PixelDemo G8 | 4950000 | 93.33 |

Chi tiết tất cả sản phẩm/score ở [demo.md](demo.md). Laptop không có RAM requirement
nên matches rỗng. Camera 50MP/64MP không OIS vẫn unknown theo rubric; không sửa
scoring để làm Demo đẹp hơn. Product detail/comparison/feedback/History đều đạt
assertions trong mỗi scenario API.

## Docker/environment validation

Kiểm tra bằng PyYAML có sẵn và Python AST (không instantiate Settings đọc secret):
YAML parse, build context/Dockerfile tồn tại, env backend đúng 19 keys, hai example
đúng defaults và provider keys rỗng; frontend build arg chỉ NEXT_PUBLIC_API_URL.
SQLite dùng `/data/smart_shopping.db` trong named volume riêng; không mount DB thật.
Healthcheck gọi backend status; frontend depends_on healthy. Ports publish loopback.
`.dockerignore` loại `.env*`, DB/WAL/SHM, venv, node_modules, .next và artifacts.

Không có Docker CLI trên máy; **không chạy được và không tuyên bố PASS** cho Compose
config interpolation thực, image pull/build, health/startup, volume permissions
hoặc container networking. README có lệnh `--env-file .env.example config/build/up`
để kiểm chứng sau trên máy có Docker. Không cài Docker trong Phase 7.

## Vấn đề còn lại và Future Work

**CRITICAL: 0; HIGH: 0 lỗi xác nhận còn mở trong local/Demo scope.**

| Ưu tiên | Mục còn lại | Hướng xử lý sau nếu được yêu cầu |
|---|---|---|
| MEDIUM | Docker runtime và Live external integration chưa xác minh | Chạy trên môi trường có Docker/API config hợp lệ; không suy ra từ mock |
| MEDIUM | Extraction tổng quát, fuzzy dedup, LLM queries/comparison còn thiếu so với SPEC | Mở rộng riêng, giữ schema và numerical authority Python |
| MEDIUM | Confidence thiếu freshness term/calibration; purpose/qualitative rules heuristic | Dữ liệu đánh giá thực và regression trước đổi công thức |
| MEDIUM | Logging/request_id/stage latency và UI progress chưa đầy đủ | Observability có correlation, tránh secrets; không giả realtime |
| MEDIUM | Comparison đã lưu trước fix có thể mang semantics cũ không xác minh | Giữ nguyên dữ liệu; chưa có provenance để phục hồi chắc chắn, cần quyết định riêng về legacy UI/repair |
| LOW | 3 thay vì 6 Home presets; 2 lint warnings; Node/pytest environment warnings | Sửa trong phạm vi phù hợp, không đổi dependencies chỉ để im warning |
| LOW | Cache expired entries chưa có cleanup job; Python chưa có lockfile; image frontend còn toolchain | Tối ưu tái lập/vận hành riêng |
| Future Work | Voice, personalization, learning từ feedback, price alerts, vector/hybrid search, multi-agent | NOT REQUIRED FOR MVP |
| Future Work | Auth/user isolation, rate limits, PostgreSQL/Redis, public deployment | MVP hiện dùng chung local DB; không đủ để triển khai công khai mà không bổ sung kiểm soát |

## Giới hạn thay đổi / Git

Không đổi SQL schema, không migration/backfill, không sửa `.env` thật hoặc
smart_shopping.db. Không đổi API/frontend routes, UI, weights, dependency/lockfile,
History/Cache semantics; không xóa/làm yếu tests. Chỉ bounded comparison HIGH fix,
regression/Demo tests và Docker/env/documentation thuộc Phase 7.

Git kiểm tra cuối gồm status, diff --name-only, diff --stat, diff --check và danh
sách untracked. Secret/artifact review chỉ trên file tracked/thay đổi dự định,
không đọc env/DB thật. Build/test artifacts ở thư mục ignored không đưa vào thay
đổi Git. Không commit hoặc bắt đầu phase mới.
