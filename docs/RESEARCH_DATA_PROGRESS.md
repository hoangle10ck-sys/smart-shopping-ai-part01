# Tiến độ Research Catalog

## R00 — DONE

- Đọc prompt/checklist, kiểm tra dirty worktree và luồng Product/Offer,
  recommendation/snapshot/comparison/cache/UI/tests.
- Xác minh schema thật bằng HEAD + 16 KiB Range HTTP 206; revision và quyền
  trong [source assessment](RESEARCH_DATA_SOURCE_ASSESSMENT.md).
- Baseline regression đang chạy; R00 là khảo sát, chưa nhập dữ liệu/chưa kết luận
  RESEARCH_DATASET_VERIFIED. Không thay đổi crawler Live.
- Tiếp theo: R01 schema additive, R02 streaming importer, R03 idempotency.

## R01 — DONE

- ResearchProduct, HistoricalPriceReference, ResearchImportRun additive; giá USD
  decimal text, price_observed_at NULL. `pytest -q tests/test_research_import.py`:
  **22 passed** (0.65s), schema native/serialized, provenance và không tạo offer.

## R02 — DONE

- JSONL/gzip streaming: file/decompressed 64 MiB, dòng 1 MiB, scan 100k,
  limit 10k; checksum, source/revision, skip/conflict stats. Cùng suite 22 passed:
  dry-run, gzip/corrupt/giant inputs.

## R03 — DONE

- Unique natural key, revision riêng, conflict không overwrite; savepoint rollback.
- Cùng suite 22 passed: import lặp, 0 offers, một reference, rollback/version.
- Baseline trước thay đổi: **938 passed** (87.87s). Chưa nhập dataset thật;
  fixtures chỉ kiểm thử offline. Tiếp theo R04 research adapter/snapshot.

## R04 — DONE

- Research API riêng, SQLite-only; dùng matcher/hard-filter/schema/snapshot cũ.
- Giá Decimal USD tách biệt; VND bị tắt budget comparison có warning. Exact specs
  priority=5 cần matched; không đủ chứng cứ trả rỗng. OfferScore=null.
- Research identities được loại khỏi live dedup, snapshot không thể rerun qua Live.
- `pytest -q tests/test_research_import.py tests/test_research_pipeline.py`:
  **26 passed** (1.55s), gồm search, USD/VND, unknown, immutable read, comparison,
  history/detail và không tạo offers. Tiếp theo R05 UI.

## R05 — DONE

- Selector Research độc lập với Demo/Live cấu hình server. Card/detail/comparison
  gắn nhãn lịch sử, giá USD/null, attribution; ẩn offer/stock/shop, điểm theo research-v1.
- Frontend **48 tests passed**, `npx tsc --noEmit`, `npm run lint`, `npm run build`
  đều exit 0. Không dùng frontend tests làm bằng chứng dữ liệu thật.
- R06 regression/browser E2E đang chạy; R07 downloader có Range cap + transport
  pin IP sẵn có; CDN `us.aws.cdn.hf.co` xác minh qua redirect từ URL chính thức.

## R06 — DONE (checkpoint, final regression sẽ chạy lại)

- Full backend **964 passed** (106.06s); frontend 48/lint/build/typecheck pass.
- Browser đầu tiên: 15 pass / 1 fail do locator chạy trước navigation detail;
  sửa test chờ URL. Rerun Research E2E **1 passed** (11.9s), không thay logic app
  để né lỗi. Đây là browser offline với fixture được gắn SYNTHETIC-TEST-ONLY.
- Thêm kiểm tra ngân sách thập phân không bị parse sai: suite research **27 passed**.

## R07 — DONE

- Download chính thức bằng HEAD + Range qua pinned egress: giữ 150 dòng mỗi file,
  tổng 1,078,165 bytes local (không raw/DB trong git); hash/revision/URLs đầy đủ
  trong `research-results/verification.json`.
- Dry-run rồi import: Electronics 75/79, Cell_Phones 75/92; bỏ 21 thiếu taxonomy.
  SQLite thực: **150 Product research, 70 historical USD price references, 0 Offers**.
- Nhập lại: 0 mới / 150 duplicate identities; giữ 150 Product và 70 references.
- `python -X utf8 -m scripts.verify_research_catalog`: 20/20 bản ghi đối chiếu raw
  độc lập với importer mapping; 3 API E2E kết quả 5/5/0, snapshot/detail/comparison/history pass.
- **RESEARCH_DATASET_VERIFIED**, không phải LIVE_VERIFIED. Mẫu có 1 điện thoại,
  3 laptop, 74 phụ kiện điện thoại; chưa có tai nghe. Không bịa mẫu bù danh mục.
- Browser trên dữ liệu thật đã chạy trong DB tạm từ cùng native prefix:
  **16 passed (42.2s)**; Research journey dùng metadata thật, các regression khác dùng fixtures.

## R08 — PARTIAL (human labels còn thiếu)

- 36 query authored + rubric + split 12 development/24 evaluation.
- `python -X utf8 -m scripts.benchmark_research` đã chạy trên SQLite thật:
  import 150/171; duplicates generated 0/150; USD budget violations 0/46;
  direct raw field support 380/380; latency p50=49.776ms/p95=75.723ms, n=108.
- Precision@5/NDCG@5/requirement accuracy/semantic explanation grounding = N/A:
  chưa có người đánh giá độc lập. Không gọi checks tự động là manual ground truth.
- JSON/CSV trong `docs/research-results`, không phải Live crawl benchmark.

### R08 — Công cụ nhận nhãn bổ sung

- Thêm `services/research/evaluation.py`, `scripts/evaluate_research_labels.py` và
  tests. Chỉ tính trên evaluation queries được gán nhãn đầy đủ, kiểm tra provenance,
  không coi nhãn thiếu là grade0. Precision mẫu số K; zero-IDCG giữ N/A.
- Đã chạy template trên catalog thật: 3.600 ô trống trong
  `backend/research-artifacts/relevance-labels.csv` (không commit).
- Đã chạy score với template trống: **LABELS_PENDING**, 0 judgments, P@5/NDCG=NULL.
- `pytest -q tests/test_research_evaluation.py tests/test_research_import.py tests/test_research_pipeline.py tests/test_research_safety.py`:
  **40 passed (2.74s)**, gồm 6 tests mới kiểm tra công thức và nhãn thiếu/provenance.
- R08 vẫn PARTIAL: cần nhãn người đánh giá độc lập thực sự; không tự điền nhãn giả.

## R09 — DONE

- README, architecture/database/testing, source assessment, rubric, integration report
  và TASKS_RESEARCH_DATA.md đã cập nhật; không đổi checklist crawler.
- Full backend cuối trước khi bổ sung công cụ nhãn độc lập: **972 passed (91.68s)**.
  Sau bổ sung công cụ: toàn bộ Research suite **40 passed**; không gọi đây là lần
  chạy full backend 978 tests.
- Frontend cuối: **48 passed**, lint và production build exit0. Build lại sau E2E
  để bỏ cấu hình API test. Browser full16 passed đã ghi phía trên.
- SQL xác nhận cuối: 150 research_products,70 historical_price_references,
  0 research offers,4 import logs. Git ignore đã kiểm tra raw/DB/artifacts.
- `git diff --check` báo whitespace có sẵn tại test_oos_recovery.py:19; giữ nguyên
  thay đổi không thuộc nhiệm vụ. Không commit/push.
- Công việc độc lập đã xử lý; còn R08 human labels và giới hạn mẫu/parser đã công bố.

## Follow-up audit — 2026-10-17: parser (DONE)

- Ngân sách được đọc trong mệnh đề tiền tệ, không lấy comparator của RAM;
  giữ cả hai đầu khoảng giá, loại trừ brand, giữ purpose và cảnh báo chưa chấm.
- Không đổi schema tiền nguyên: ngân sách thập phân/mixed currency/ambiguous
  trả lỗi rõ ràng, không tự làm tròn hay quy đổi.
- `pytest -q tests/test_research_parser_regressions.py tests/test_research_pipeline.py`:
  **24 passed (2.30s)**, gồm 19 regression cases mới và integration SQLite/API.
- Tiếp theo: mở rộng mẫu theo nhóm thiết bị, UX, đo lại R08; human labels vẫn thiếu.

## Follow-up — catalog expansion (DONE)

- Tải bounded Range tối đa 4 MiB/file từ revision chính thức, 900 dòng/file;
  sandbox ConnectError, chạy lại có cấp quyền network thành công HTTP206.
- Bổ sung headphone leaf taxonomy và importer quota có tests; giữ nguyên mọi
  bản ghi/snapshot cũ. Chọn tối đa 20 laptop,20 tai nghe,10 điện thoại trong prefix.
- `python -m scripts.expand_research_catalog`: thêm **41 Product,18 historical prices**;
  tổng **191 Product,88 prices,0 research Offers**. Lặp import: **0 mới/46 duplicate**.
- Catalog: 6 điện thoại,20 laptop,19 tai nghe; 103 sản phẩm thiếu giá. Chưa đủ
  quota điện thoại vì prefix chỉ có 6 identity; không tự tạo mẫu bù.
- `pytest -q tests/test_research_import.py tests/test_research_safety.py`: **33 passed**.
- `python -m scripts.verify_research_catalog --extra-data-dir data/research-expanded --report ../docs/research-results/expanded/verification.json`:
  đối chiếu **191/191 raw records**, 3 API journeys 5/5/0, không có offer giả.
- Raw mở rộng được git/docker ignore; provenance hash và dòng gốc vẫn được giữ.

## Follow-up — UX (implementation done, browser verification pending)

- Hiển thị lỗi validation API thay cho lỗi kết nối chung; bộ lọc/sort Research
  dùng historical USD với nhãn riêng, không dùng ProductOffer, missing price bị loại khi lọc.
- Refresh Research thực sự tạo snapshot mới từ nhu cầu đã lưu; snapshot cũ giữ nguyên.
- `npm test`: **48 passed**; thêm browser regressions cho validation/filter/refresh.
- Tiếp theo: chạy browser/full regression và đo lại benchmark R08.

## Follow-up — ABO Research catalog (2026-10-29)

- User approved adding at most 200 Amazon Berkeley Objects (ABO) catalog records to
  `HISTORICAL_RESEARCH`; keep the prior catalog intact and do not create prices/offers.
- Official public ABO listing metadata and image metadata downloaded over HTTPS;
  selected **136/200** records from 147,702 scanned. Category quotas yielded 25
  phone accessories, 25 headphones, 25 computer accessories, 25 mice, 25 keyboards,
  9 laptops, 1 monitor, and 1 phone. No synthetic fill was added for scarce categories.
- Attribution: Amazon Berkeley Objects, CC BY 4.0. Sample manifest has catalog SHA-256
  `7dd79faf06039474c6a105e4ffea6b76e122a6f65b123da2ac739bd2cd147e2e` and object ETags;
  raw files and manifest are kept under ignored `backend/data/research/abo/`.
- Added a separate bounded ABO importer and download/import scripts. Existing Amazon
  Reviews importer remains unchanged. Default Research search now includes all imported
  research datasets (explicit revision filter remains supported); UI shows dataset and
  ABO license attribution. ABO values do not populate rating, review count, price, or offer.
- PostgreSQL target was confirmed as local `smart_shopping`; existing Compose volume was
  reused without migrations/schema changes. Before: 31 products / 0 research products /
  32 offers / 0 historical prices. After additive import: **167 products / 136 research
  products / 32 offers / 0 historical prices**. Import report: 136 imported, 0 skipped,
  0 duplicate, 0 offers created, 0 prices created. Existing 31 products and 32 offers kept.
- Live verification: 136 ABO rows in DB, 120 have an image URL, all 136 have metadata
  specifications, 0 have rating/review values. Five sampled image URLs returned HTTP 206
  `image/jpeg`. A laptop Research query returned 5 ABO recommendations. This verifies
  public dataset images and research retrieval only; commerce Live remains unverified.
- Targeted `pytest ...research... tests/unit/test_unified_search_service.py`: **101 passed**;
  full backend `pytest -q`: **1046 passed in 78.97s** (exit 0). Frontend `npm test`:
  **65 passed**; `npx tsc --noEmit`, `npm run lint`, and `npm run build`: exit 0.
- `git diff --check`: exit 0; only Git LF→CRLF advisories, no whitespace errors. Final
  diff reviewed for task files; unrelated pre-existing dirty files were preserved.

## Follow-up — ABO taxonomy coverage (2026-10-29)

- Read-only profile of the official ABO listing shards scanned 147,702 records and
  found 576 source product types. Frequent uncovered types included shoes (12,965),
  grocery (6,546), home (5,264), pets (1,064), sports (972); source also had 5 TVs
  and 4 refrigerators.
- Added specific mappings for `SHOES`, `GROCERY`, `HOME`, `PET_SUPPLIES`,
  `SPORTING_GOODS`, `TELEVISION`, and `REFRIGERATOR`; aligned the deterministic
  fallback, source category normalizer, and Research query parser. Regression checks
  cover type mapping, category recognition, and end-to-end Research filtering.
- Added only the remaining **64 image-backed ABO records**, excluding IDs already in
  the first sample: 16 shoes, 12 grocery, 12 home, 8 pets, 7 sports, 5 TVs, 4 fridges.
  The official-source sample now reaches the approved cap of **200**; no new prices,
  offers, ratings, or review counts were generated.
- PostgreSQL read-only verification after import and full tests: **231 products / 200
  ABO ResearchProduct / 32 existing offers / 0 historical prices / 2 ABO import runs**.
  184/200 ABO entries have image URLs; all have source-derived metadata. Seven category
  queries returned only their matching category (5 results each where available; 4 fridges).
  Five image URLs from this extension returned HTTP 206 `image/jpeg`.
- Targeted category/parser/normalizer suite: **92 passed**; final full backend:
  **1076 passed (79.78s), exit 0**.
  Test isolation was confirmed in `backend/tests/conftest.py`; tests use a disposable
  SQLite file and refuse a non-test engine URL. No frontend code changed in this phase.
- Human relevance judgments are still needed before Precision@K/NDCG@K can be reported;
  catalog coverage and parser regression tests do not establish recommendation quality.

## Follow-up — Open Facts bounded Research sample (2026-10-29)

- User approved a small Research-only sample with attribution and no current prices,
  stock, rating, review count, or merchant Offers. Existing data was retained.
- Production Open Food Facts query `coffee`, maximum 25: HTTP 503. No retry; no food
  rows imported. Earlier staging verification is not evidence of current production
  availability.
- Production Open Products Facts query `laptop`, maximum 25: HTTP 200, 11 records;
  11 had a name and valid barcode, 7 had official image URLs. Six records had an
  explicit Laptop category; remaining products were kept unclassified instead of
  assigning a category from the search term.
- Added an offline importer and downloader with a 25-record cap per dataset, sample
  checksum/revision, source-host image validation, duplicate protection across
  revisions, and ResearchImportRun audit entry. No schema/migration changes.
- Attribution is stored and shown in Research UI: Open Facts source, ODbL 1.0, DbCL
  v1.0, and CC BY-SA 4.0 for image-bearing records. A source product page is available
  for checking its catalog record; it is not a merchant purchase link.
- Local Compose PostgreSQL before/after: 231/242 products, 200/211 Research products,
  2/3 Research import runs; 32/32 offers and 0/0 historical prices. Import report:
  11 imported, 0 skipped/duplicate, 7 images, 0 offers, 0 prices.
- Target tests: backend 11 passed; frontend Research attribution 6 passed. Full backend
  regression: 1104 passed (91.37s), exit 0. Full frontend tests: 71 passed, exit 0;
  lint, TypeScript check, and production build exit 0. Two sampled OPF image URLs
  returned HTTP 200 `image/jpeg`. Compose backend/frontend rebuild and start exited 0;
  product detail API and frontend root both returned HTTP 200. Playwright rendered the
  OPF product name and both license attributions without page errors (exit 0). Commerce
  Live remains `LIVE_NOT_VERIFIED`; Open Products Facts is an experimental Research
  source.

## Follow-up — Research source labels (2026-10-29)

- Corrected a UI semantics issue: Open Facts catalog records are community-contributed
  reference data, not necessarily historical datasets. Product notices and the results
  mode badge now distinguish Open Facts from historical sources such as ABO; price,
  stock, and seller availability remain explicitly unverified. Mixed Research results
  get a separate label.
- Regression first reproduced the incorrect label (FAIL), then target tests passed:
  `research.test.mjs` and `results-utils.test.mjs`, **22 passed**. Full frontend suite:
  **71 passed**. `npm run lint`, `npx tsc --noEmit`, and `npm run build` each exited 0.
- `docker compose build frontend` completed exit 0. Container replacement failed with
  Docker Desktop containerd metadata-store `input/output error`; Docker Desktop's WSL
  bootstrap then failed with `0xc00000fd`. A local restart briefly restored the daemon,
  but it failed again. The containers became unresponsive; no volume was removed or
  reset. Runtime browser verification for this label correction is therefore
  `BLOCKED`; local test/build results do not establish that the updated container is
  serving the UI.
- Runtime diagnosis: the frontend container exited because `/app/node_modules/next/package.json`
  inside the image was 0 bytes (`ERR_INVALID_PACKAGE_CONFIG`); the host package file is
  valid (`next` 16.4.1). `docker compose build --no-cache frontend` completed `npm ci`
  (371 packages) but BuildKit ended with an RPC EOF before a final build result.
  Docker Desktop/WSL then stopped again. Frontend runtime verification remains blocked;
  no Docker data volume was reset or removed.
- Added a final-image build guard in `frontend/Dockerfile` to parse and validate the
  Next.js package metadata after runtime-layer copy. This guard is not yet verified by
  a Docker build because Docker Desktop/WSL is unavailable.

## Follow-up — Docker runtime recovery check (2026-10-30)

- Rechecked the runtime after resuming: `docker version` exited 1 (`Docker Desktop is
  unable to start`); WSL reports both `Ubuntu` and `docker-desktop` as `Stopped`.
- Local probes to `http://127.0.0.1:3000` and `http://127.0.0.1:8000/api/system/status`
  both failed; there is no frontend/backend process available for browser integration
  verification outside Docker.
- Docker Desktop/backend processes are present, but `com.docker.service` is stopped.
  Attempting `Start-Service com.docker.service` exited 1 because this session cannot
  open the service. No Docker restart/reset, volume operation, or database mutation was
  performed in this check.
- Frontend local regression: `npm test` **71 passed, exit 0**;
  `npm run lint` **exit 0**; `npx tsc --noEmit` **exit 0**. `git diff --check` **exit 0**
  (Git emitted only LF-to-CRLF advisories).
- Runtime image build and browser verification remain `BLOCKED` by Docker Desktop's
  unavailable engine. The Dockerfile metadata guard remains `CODE_INSPECTED`, not
  runtime-verified. Existing Docker volumes and dirty worktree files were preserved.

## Follow-up — Frontend container recovery (2026-10-30)

- Reproduced against the existing frontend image: `/app/node_modules/next/package.json`
  was **0 bytes** and Node failed with `ERR_INVALID_PACKAGE_CONFIG` (exit 1). The host
  dependency file was valid (3,188 bytes, Next.js 16.4.1), and root `.dockerignore`
  already excludes `node_modules` and `.next`; no host dependency copy caused the image
  defect. The precise underlying Docker storage failure was not established.
- Ran `docker compose build --no-cache frontend`: **exit 0**. Production Next build,
  TypeScript phase, and final runtime-image metadata guard all completed successfully.
  A disposable container check confirmed the rebuilt image has a 3,188-byte package
  file and Next.js 16.4.1 (`docker run --rm ...` exit 0).
- Ran `docker compose up -d frontend`: **exit 0**. Compose reports frontend Up, backend
  and PostgreSQL healthy, and SearXNG running. No volume reset or database operation was
  performed.
- Runtime checks: frontend `/` returned HTTP 200; backend `/api/system/status` returned
  HTTP 200. Playwright Edge smoke against the Docker frontend returned HTTP 200, rendered
  the expected page title and heading, with **0 page errors** (exit 0). Frontend logs
  show Next.js 16.4.1 ready and no package-config error.
- The displayed container failure is resolved and runtime-verified. The image guard
  catches invalid Next.js package metadata during future builds; the prior Docker
  storage/I/O incident's underlying cause remains unknown.

## Follow-up — Research path regression and remaining R08 gate (2026-10-30)

- Confirmed backend pytest isolation from `backend/tests/conftest.py`: each run sets
  `DATABASE_URL` to a newly created temporary SQLite file, asserts the SQLAlchemy engine
  points to that file, and disables external providers and Live collection before app
  imports. No developer or Compose database was used by these tests.
- Research target command:
  `python -B -m pytest -q tests/test_research_evaluation.py tests/test_research_import.py tests/test_research_pipeline.py tests/test_research_safety.py` —
  **50 passed (2.69s), exit 0**.
- First full backend run found one timing-sensitive existing regression test: its 20 ms
  deadline could expire before the mocked recovery probe began under suite load (1104
  passed, 1 failed). Increased only that test's startup window while preserving the
  hanging-probe cancellation/no-retry assertions. Targeted recovery file: **23 passed
  (7.55s), exit 0**; rerun full backend: **1105 passed (88.84s), exit 0**.
- Frontend checks: `npm test` **71 passed, exit 0**; `npm run lint` **exit 0**;
  `npx tsc --noEmit` **exit 0**; `npm run build` **exit 0**.
- Browser E2E: `npm run test:e2e -- --reporter=list` **23 passed (52.6s), exit 0**.
  `backend/scripts/run_e2e_backend.py` was inspected: E2E uses a disposable temporary
  SQLite DB, Demo-only settings, and a loopback-only network guard. Test journeys include
  unified search/results/detail/comparison/history, validation/error states, and four
  responsive widths. Separate Docker runtime smoke also passed above.
- `R08` remains **PARTIAL / LABELS_PENDING**: the 24 evaluation queries still need
  independent human relevance judgments before Precision@5/NDCG@5 or semantic grounding
  can be reported. No labels were fabricated. Catalog and regression metrics do not
  replace human quality judgments. Commerce prices/stock remain `LIVE_NOT_VERIFIED`.
- Next action within this research plan: obtain independent labels using
  `docs/RESEARCH_BENCHMARK_RUBRIC.md`, then run the documented evaluator. The other
  software-verifiable Research path checks are complete for this checkpoint.

## In progress — Verified product-image eligibility (2026-10-30)

- User approved enforcing verified-image eligibility and the additive comparison API
  evidence schema. Recommendation, product-detail, research-search, comparison-create,
  and comparison-read paths now require matching `image_url` / `image_evidence`; old
  snapshots without evidence are filtered. Image evidence expires for API eligibility
  after 24 hours. Products sharing one image hash across distinct product IDs are
  conservatively excluded as ambiguous.
- Image probes download the complete bounded raster (8 MiB maximum), check HTTP/MIME
  and raster signature, record a SHA-256 and timestamp, and do not follow redirects to
  unapproved hosts. Research images also require a supported dataset, source record,
  identifier and applicable image license. UI has no placeholder fallback; cards and
  comparisons hide products when evidence is absent, mismatched, or the browser cannot
  load the image.
- Read-only Compose PostgreSQL inventory found 242 products, 191 image URLs, and 51
  products without URLs. Live byte audit (`backend/scripts/audit_product_images.py`)
  rechecked all 191 URLs: **180 eligible**, **11 rejected**. Reasons: 10
  `IMAGE_DUPLICATE_IDENTITY_CONFLICT` across duplicate-hash groups `[55,74,85,118]`,
  `[64,114]`, `[72,89]`, `[113,145]`; and product 236
  `IMAGE_IDENTITY_UNVERIFIED` (invalid GTIN). No database rows were updated.
- Checks after the policy change: backend targeted tests **164 passed, exit 0**;
  frontend tests **73 passed, exit 0**; `npx tsc --noEmit` **exit 0**; targeted ESLint
  **exit 0**. A full backend run before the last compatibility/test updates had
  **1015 passed, 100 failed, exit 1**; most failures exercise catalog/test fixtures
  without verified image evidence or the former Range-only probe contract. A full
  backend rerun after the latest changes remains **NOT RUN**. This track is not complete
  until regression failures are resolved or precisely separated into expected behavior
  changes, and full verification is repeated.
- Live audit verifies source linkage and image bytes, but no human visually inspected
  every image. The 24-hour evidence window and duplicate-hash exclusion are conservative
  rules; duplicate records require source-data cleanup or stronger product-variant
  evidence before they can be eligible again.

## Follow-up — Verified image gate completed (2026-10-30)

- Fixed the retrieval handoff that retained only an image-load boolean and discarded the
  actual byte probe. Product-page evidence now carries the probe through recommendation
  snapshots and comparison responses. A verified same-page product name is accepted as
  the identity anchor when a manufacturer model is absent; generic/unbound image URLs
  remain ineligible.
- Applied the eligibility rule to search, recommendations, details, research results,
  and both comparison API reads and writes. The frontend hides products on missing,
  mismatched, duplicate, or failed images and never substitutes a placeholder. Legacy
  snapshots without image proof are excluded. Comparison schema/API changes are additive
  and were implemented after the user's explicit approval.
- Read-only inventory: **242 products**; **191** had image URLs and were probed from
  their recorded source datasets; **180 verified eligible** and **11 rejected**. The
  other **51** products had no image URL. Across the full inventory: **180 eligible**,
  **62 excluded** — 51 missing images, 10 duplicate-image identity conflicts in four
  groups, and product 236 with an invalid GTIN. No database rows were modified. The
  audit validates source identifiers/provenance, image HTTP response, raster bytes,
  MIME and digest; it does not claim a human visually inspected all 191 images.
- Final checks: backend full suite **1118 passed (108.15s), exit 0**; frontend
  `npm.cmd test` **73 passed, exit 0**; `npm.cmd run lint`, `npx.cmd tsc --noEmit`,
  and `npm.cmd run build` **exit 0**; Playwright E2E **23 passed (57.3s), exit 0**;
  `git diff --check` **exit 0** (Git printed only existing LF/CRLF advisories).
- E2E uses an isolated disposable SQLite database, blocks external network access, and
  serves a one-pixel PNG only for the reserved `qa-catalog.example` fixture host. The
  broken-image journey verifies the product is removed and comparison becomes
  unavailable when fewer than two verified images remain.
- Image eligibility implementation is complete for this checkpoint. Commercial prices,
  stock, and ratings are not verified by this image audit; historical records and
  `LIVE_NOT_VERIFIED` labels retain their existing meaning. Human visual spot-checks and
  source cleanup for the duplicate/invalid-identifier records remain follow-up data work.
