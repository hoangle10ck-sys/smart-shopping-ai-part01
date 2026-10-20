# TASKS_RESEARCH_DATA.md — Smart Shopping AI: Research Catalog (Mục tiêu A)

> Trạng thái ban đầu: TODO. Đây là **luồng dữ liệu nghiên cứu** độc lập với crawler Live. KHÔNG sửa trạng thái T02/T05/T09 của crawler Live thành DONE để thay thế. Không được biến dữ liệu lịch sử thành dữ liệu đang bán.
>
> Repo đích: `ThinhLoLem/smart-shopping-ai-part01`. Kiểm tra working tree và phiên bản mã nguồn trên máy trước khi sửa.
>
> Nguyên tắc vận hành: làm lần lượt R00–R09; cập nhật checklist + `docs/RESEARCH_DATA_PROGRESS.md` sau từng nhiệm vụ; mỗi DONE phải có bằng chứng kiểm thử; tiếp tục việc độc lập nếu bị chặn.

## Đích nghiệm thu

- [x] Catalog chứa 100–200 **sản phẩm điện tử thật**, được đọc từ tệp metadata gốc (không mock, không tạo giả bằng LLM), sau khi xác minh phạm vi nghiên cứu và điều kiện sử dụng.
- [x] Ít nhất hai nhóm sản phẩm phù hợp với đề tài (ví dụ thiết bị điện tử, điện thoại/phụ kiện); báo chính xác số lượng và tỷ lệ sản phẩm có giá, không ép đủ mẫu giá.
- [x] Ghi nguồn/dataset version/checksum/ID/provenance; không bịa merchant, offer, SKU, thời gian giá, tồn kho hoặc tiền tệ.
- [x] Cùng dữ liệu đầu vào import hai lần => không tăng số dòng product/price reference trùng; kết quả deterministic.
- [x] Người dùng nhập nhu cầu => tìm catalog nội bộ => hard filter/score/rank => so sánh => giải thích có bằng chứng, và giao diện gắn nhãn `HISTORICAL_RESEARCH`.
- [x] Demo Mock và Tavily Live vẫn hoạt động; nguồn research không ảnh hưởng `LIVE_VERIFIED` hoặc cờ crawler Live.
- [x] Unit, integration, UI tests; benchmark thực nghiệm có mẫu số và nguồn gốc, không báo fixture là dữ liệu Live.

## R00 — Khảo sát mã nguồn và tập dữ liệu (P0)

Trạng thái: **DONE** — bằng chứng schema thật, revision/quyền và thiết kế tối thiểu
trong `docs/RESEARCH_DATA_SOURCE_ASSESSMENT.md`; checkpoint tại `docs/RESEARCH_DATA_PROGRESS.md`.

- [x] Đọc README, TASKS hiện có nếu tồn tại, docs, models Product/ProductOffer/Source/RawProductCandidate, cache, filter, scoring, recommendation, comparison, frontend, cấu hình và tests. Không dựa vào tên file đoán trước.
- [x] Kiểm tra `git status`; không ghi đè thay đổi chưa commit; tạo kế hoạch thay đổi tối thiểu.
- [x] Đọc [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023), [native JSONL](https://amazon-reviews-2023.github.io/data_loading/jsonl.html), [discussion quyền sử dụng](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1).
- [x] Kiểm tra điều kiện sử dụng cho đồ án **nghiên cứu phi thương mại** trước khi tải/import; ghi tài liệu nguồn, ngày kiểm tra, giới hạn, trích dẫn. Không tuyên bố bộ Amazon Reviews 2023 có giấy phép mở rõ ràng: nhóm xuất bản không có quyền tự cấp giấy phép toàn bộ dataset; trao đổi trên diễn đàn nói không phản đối sử dụng cho luận văn, không phải quyền tái phân phối.
- [ ] Nếu phạm vi sử dụng không phù hợp/chưa được giải quyết, không tự suy diễn chấp thuận; báo `BLOCKED_RIGHTS` và chuẩn bị adapter dự phòng từ [Amazon Berkeley Objects — CC BY 4.0](https://amazon-berkeley-objects.s3.amazonaws.com/index.html) (catalog metadata thật, **không có giá bán phù hợp**). (Không áp dụng: phạm vi nghiên cứu được ghi nhận trong assessment.)

**Done:** Có `docs/RESEARCH_DATA_SOURCE_ASSESSMENT.md`, mapping đã kiểm tra trên metadata thật, quyết định nguồn rõ ràng.

## R01 — Thiết kế provenance, dữ liệu và tiền tệ (P0)

Trạng thái: **DONE** — schema/provenance/giá riêng; 22 tests trong checkpoint R01–R03.

- [x] Thêm source mode: `MOCK_DEMO`, `HISTORICAL_RESEARCH`, `LIVE_VERIFIED` hoặc mapping thống nhất với mode hiện tại; không nhập nhằng.
- [x] Xác định identity `(dataset_id, dataset_version/revision, parent_asin)` cho sản phẩm metadata Amazon Reviews 2023; kiểm tra duplicate/variant ambiguous. **Không suy ra SKU** từ `parent_asin`.
- [x] Dữ liệu `title`, `main_category`, `average_rating`, `rating_number`, `features`, `description`, `images`, `store`, `categories`, `details`, `price`, `parent_asin`; xử lý cấu trúc thật theo JSONL native (khác bản `datasets` loader một số trường có thể bị serialize).
- [x] Metadata `store` không tự động tương đương người bán hiện đang bán; không tạo merchant hoặc shop trust score từ trường này.
- [x] Thiết kế bảng hoặc bản ghi `historical_price_reference` riêng với `amount`, `currency`, `source`, `reference_year`, `price_observed_at nullable`, `imported_at`, `provenance`; **không tạo ProductOffer đang mua được** chỉ để khớp DB hiện tại.
- [x] Với giá thiếu/rỗng/'None'/không hợp lệ => `NULL`; giá là giá snapshot lịch sử, không phải giao dịch đã kiểm chứng. Chỉ gắn `USD` khi nguồn/context metadata đã xác minh là giá USD; nếu không thì currency unknown và không xếp hạng theo giá.
- [x] `imported_at` là thời gian nhập, KHÔNG là thời gian giá được quan sát. Nếu chỉ biết bộ dữ liệu được thu thập năm 2023, lưu `reference_year=2023`; `price_observed_at=NULL`.
- [x] Ngân sách VND: không so với giá USD nếu thiếu FX hợp lệ, có ngày hiệu lực và trạng thái quy đổi minh bạch. MVP cho phép research queries theo USD hoặc tắt budget comparison với chú thích.

**Done:** Mô hình dữ liệu nhất quán, có migration nếu thay schema và tests cho tiền tệ/timestamp.

## R02 — Importer JSONL an toàn, streaming (P0)

Trạng thái: **DONE** — bounded JSONL/gzip + CLI, 22 tests offline.

- [x] Tạo `backend/scripts/import_research_catalog.py` hoặc module phù hợp thực tế.
- [x] Input từ file local JSONL/JSONL.gz đã tải riêng bằng workflow được phép, không tự tải hàng trăm GB. Ưu tiên chỉ metadata Electronics và Cell_Phones_and_Accessories; không cần review files ở MVP.
- [x] Tuyệt đối không dùng `eval`, `trust_remote_code=True` hoặc chạy code từ dataset không kiểm tra. Dùng `json.loads`, `gzip.open` nếu nén, streaming từng dòng, giới hạn file/line size, số record, memory, log errors.
- [x] Config CLI rõ ràng: `--input`, `--dataset`, `--category`, `--limit`, `--dry-run`, `--report` và tùy chọn seed/selection. Không giả định flag có sẵn nếu chưa cài.
- [x] Mapping category/brand/specifications bảo thủ; với cell phone cần phân biệt thiết bị điện thoại và case/ốp lưng/cáp sạc bằng taxonomy + evidence; không suy diễn brand/model.
- [x] Lọc sản phẩm có tên có ý nghĩa, identity, evidence. Để 100–200 record *đủ dùng*, chọn stratified sample minh bạch, không lấy ngẫu nhiên tràn lan và không bổ sung dữ liệu tưởng tượng.
- [x] Tạo checksum SHA-256 input, metadata version/revision, nguồn download, imported count, skipped count, error reasons; không commit raw dataset nếu quyền không cho phép.

**Done:** Dry-run và import cùng một tệp nhỏ hợp lệ cho kết quả thống kê xác minh được.

## R03 — SQLite ingestion/idempotency (P0)

Trạng thái: **DONE** — natural key/revision/conflict/savepoint, idempotency tests pass.

- [x] Kiểm tra cấu trúc ORM hiện tại, tích hợp catalog research bằng migration không phá dữ liệu cũ.
- [x] Unique constraint trên natural key `(dataset, version, external_product_id)`; upsert deterministic.
- [x] Lưu Product metadata, source attribution và historical reference price nếu có. Không tạo seller/offer/buy link/tồn kho giả.
- [x] Nếu cần giữ nhiều phiên bản dữ liệu, version theo dataset revision, không ghi đè im lặng provenance.
- [x] Rerun import: không tăng số product/reference trùng. DB rollback an toàn nếu lỗi giữa batch.
- [x] Tách `research import logs` khỏi crawl logs Live.

**Done:** Import lặp 2 lần idempotent, truy vấn SQLite đếm và kiểm chứng provenance được.

## R04 — Search và recommendation cho Research Mode (P0)

Audit follow-up 2026-10-17: đã sửa phạm vi comparator ngân sách/RAM, khoảng giá,
brand phủ định và purpose disclosure; parser + API regression **24 passed**.

Trạng thái: **DONE** — 26 tests import/pipeline pass; R07 sẽ đo dữ liệu thật riêng.

- [x] Cho user chọn `Research Catalog (dữ liệu lịch sử)` độc lập với Demo/Live.
- [x] Nhu cầu tiếng Việt -> category + keywords -> truy vấn catalog SQLite; không gọi crawler Live khi chọn Research mode.
- [x] Adapt `CandidateBuilder` hoặc thêm adapter đúng cách để xử lý product không có merchant offer; không fake RawProductCandidate được xác minh từ trang bán hàng để vượt validation hiện có.
- [x] Hard filter: unknown specs không coi là đạt, exact RAM/storage chỉ khi evidence đủ; giá USD phải có budget USD tương ứng để lọc.
- [x] Tách `ProductSuitabilityScore` khỏi `OfferScore`; với catalog research **OfferScore = N/A** (không bán), không cộng điểm shop/ship/stock giả.
- [x] Lưu immutable recommendation snapshot + metadata provenance/mode. Các kết quả cũ vẫn đọc được.
- [x] LLM explanation chỉ từ evidence; deterministic fallback khi không API key; không diễn giải giá lịch sử thành giá hiện tại.

**Done:** End-to-end cho ít nhất 3 nhu cầu, có kết quả/không kết quả hợp lý và không đánh tráo lịch sử với Live.

## R05 — Frontend/comparison (P1)

Audit follow-up: sửa thông báo validation, lọc/sort giá lịch sử và refresh snapshot;
frontend unit48 pass, browser regressions đang kiểm tra (xem progress).

Trạng thái: **DONE** — 48 frontend tests + lint/typecheck/build pass; browser E2E tại R06.

- [x] Bộ chọn mode rõ ràng: Demo / Research (historical) / Live (nếu được phép).
- [x] Nhãn nhìn thấy trên mọi thẻ/bảng: `Dữ liệu nghiên cứu (2023) — không phải giá bán hiện tại`.
- [x] Nếu giá có: `Giá tham khảo lịch sử (USD)`; nếu không: `Chưa có giá trong dataset`.
- [x] Ẩn/vô hiệu `Mua ngay`, vận chuyển, stock, seller reliability/offer score khi source research không hỗ trợ.
- [x] Hiển thị ảnh/link nguồn với attribution và security sanitization; không đảm bảo sản phẩm Amazon hiện còn tồn tại/giá giống cũ.
- [x] So sánh thông số và requirement match, rating/review count khi có; giải thích unknown riêng.

**Done:** UI render đúng trạng thái, an toàn, snapshot/history không sai sematics.

## R06 — Tests an toàn & offline (P0)

Trạng thái: **DONE** — full backend972 pass; sau thêm công cụ nhãn, Research40 pass;
frontend48 pass, lint/build pass, browser16 pass (Research dùng prefix thật).

- [x] Unit: JSONL parsing, `null` price, tiền tệ, category, variants, URL, provenance, checksum, import stats, sample selection.
- [x] Integration: local fixture => SQLite => research search => score/rank => snapshot => comparison => history.
- [x] Negative: repeated import, corrupt JSON, duplicate parent_asin, giant record, bad currency, unknown price, missing category, no offers, legacy DB.
- [x] Regression: toàn bộ test repo + frontend test/lint/build nếu môi trường cho phép.
- [x] Default tests không tải internet và không chạy dataset code tùy ý.

**Done:** Test commands và counts được ghi có thật vào report.

## R07 — Dataset ingestion thật (P0)

Audit follow-up: mở rộng thành **191 Product / 88 historical prices / 0 Offers**;
6 điện thoại,20 laptop,19 tai nghe. Repeat: 0 mới. Audit raw **191/191** pass.
Reports mới ở `docs/research-results/expanded/`; báo cáo 150-record cũ giữ làm baseline.

Trạng thái: **DONE / RESEARCH_DATASET_VERIFIED** — 150 Product, 70 historical prices,
0 Offers; 20 raw checks, repeat ingestion, 3 API E2E pass. Xem verification.json.

- [x] Theo quyền cho phép, tải file metadata chính thức từ nguồn đã xác minh (có thể lớn: chỉ metadata, kiểm tra kích thước/trước tải); không import sample code vô danh.
- [x] Chạy import 100–200 sản phẩm điện tử thật; báo bao nhiêu name/brand/category/price/rating/images đầy đủ, phân phối danh mục, USD/unknown.
- [x] Kiểm tra ngẫu nhiên ít nhất 20 record so với JSONL gốc; số liệu là dataset thật, không phải web Live.
- [x] Import lại, kiểm tra không trùng; chạy 3 E2E queries.
- [x] Ghi `RESEARCH_DATASET_VERIFIED` sau khi kiểm tra nguồn + bản ghi nhập, không đổi crawler status `LIVE_NOT_VERIFIED`.

**Done:** Có report thực nghiệm và DB chứa dữ liệu thật theo cơ chế research, rõ xuất xứ/giới hạn.

## R08 — Benchmark recommender (P1)

Audit follow-up: chạy cohort191 với42 queries, kiểm tra cả hai đầu khoảng giá và
6 parser contract cases; template mới4.584 ô. **PARTIAL / LABELS_PENDING**:
không có human relevance labels; không coi regression expectations là human labels.
Kết quả hiện hành trong `docs/research-results/expanded/`.

Trạng thái: **PARTIAL** — 36 queries, benchmark JSON/CSV thật đã chạy;
chưa có human labels độc lập, Precision@5/NDCG@5/accuracy/semantic grounding N/A.
Đã có công cụ template/score, 3.600 ô nhãn trống và kiểm thử nhãn thiếu/provenance;
chạy thực với template trống giữ LABELS_PENDING.

- [ ] Lập bộ 30–50 truy vấn nhu cầu có rubric gán nhãn thủ công, split đánh giá rõ ràng, không ngụy tạo ground truth.
- [ ] Đo Catalog import success, field completeness, duplicate rate, budget constraint violations, requirement match accuracy, Precision@K, NDCG@K, p50/p95 ranking latency, explanation grounding rate.
- [x] Lưu dataset provenance, mẫu số mỗi metric, script và kết quả JSON/CSV; không gọi metrics này là `LIVE CRAWL SUCCESS`.

**Done:** Report có command tái lập và số liệu quan sát thật hoặc N/A minh bạch.

## R09 — Final audit, docs, checkpoint (P1)

Trạng thái: **DONE** — báo cáo/checkpoint cuối đã ghi các kết quả thực tế và phần R08 còn thiếu.

- [x] Update README, docs/architecture/database/testing và `docs/RESEARCH_DATA_INTEGRATION_REPORT.md`.
- [x] Hiển thị rõ sự khác biệt `MOCK_DEMO` / `HISTORICAL_RESEARCH` / `LIVE_VERIFIED`.
- [x] Cập nhật `docs/RESEARCH_DATA_PROGRESS.md`: DONE/PARTIAL/BLOCKED, lệnh, test result, metadata file provenance, outstanding tasks.
- [x] Không ghi đè TASKS.md của crawler; cập nhật file này và dẫn liên kết từ README/TASKS chính nếu hợp lý.
- [x] Không tự push. Báo cáo cuối bằng tiếng Việt, chỉ kết luận những gì đã chạy.

**Done:** Có cách chạy lại trên máy khác với dữ liệu cung cấp hợp lệ và tình trạng hoàn thành thực tế.

---

## Checkpoint sau mỗi pha

Cập nhật `docs/RESEARCH_DATA_PROGRESS.md` với:

```text
Task ID:
Status: TODO | IN_PROGRESS | DONE | BLOCKED
Changed files:
Commands run:
Tests: pass/fail/not-run + reasons
Real dataset source/version:
Records imported / skipped / duplicate:
Open issues:
Next task:
```

## Các trạng thái không được đánh đồng

- `MOCK_TESTED`: dữ liệu tổng hợp để kiểm thử.
- `RESEARCH_DATASET_VERIFIED`: đã nhập và kiểm tra dữ liệu sản phẩm thực từ bộ nghiên cứu, **không phải giá bán hiện tại**.
- `HISTORICAL_PRICE_AVAILABLE`: chỉ có giá tham khảo lịch sử, không có chứng cứ seller/availability.
- `LIVE_VERIFIED`: chỉ dành cho crawler/seller price đã trực tiếp xác minh hiện hành qua nguồn được phép.
- `BLOCKED_RIGHTS`, `BLOCKED_DATA`, `BLOCKED_RUNTIME`: phải có lý do và phương án tiếp tục.
