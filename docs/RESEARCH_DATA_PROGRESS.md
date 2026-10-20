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
