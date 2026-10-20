# Báo cáo tích hợp Research Catalog — Mục tiêu A

## Cập nhật sau audit

Đã mở rộng lên **191 Product / 88 historical USD prices / 0 research Offers**,
sửa parser ngân sách/brand phủ định, bổ sung headphone taxonomy và UX. Báo cáo
hiện hành: [Follow-up audit](RESEARCH_FOLLOWUP_REPORT.md). Các số liệu150-record
phía dưới là baseline trước mở rộng, không phải số hiện tại.

Ngày: 2026-10-17. **RESEARCH_DATASET_VERIFIED**, không LIVE_VERIFIED.
R00–R07 đã thực hiện; R08 có benchmark tự động nhưng thiếu nhãn đánh giá thủ công
độc lập, không tuyên bố hoàn tất chất lượng recommender. R09 ghi tài liệu/checkpoint.
Không push, không bật Live flags, không ghi đè thay đổi crawler trước đó.

## Dữ liệu thật đã nhập

Nguồn: [McAuley Lab / Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023).
Revision: `2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e`.
[Căn cứ phạm vi nghiên cứu](RESEARCH_DATA_SOURCE_ASSESSMENT.md) không phải giấy phép
mở/tái phân phối. Raw prefix và SQLite giữ cục bộ, git/Docker bỏ qua.

HEAD Electronics: 5,246,144,134 bytes; Cell_Phones: 4,015,159,840 bytes.
Download Range 206, cap 4 MiB/file, dừng sau 150 dòng hoàn chỉnh/file;
giữ 548,643 + 529,522 = 1,078,165 bytes. Download sử dụng connection-time pinned
transport sẵn có, allowlist official HF/CDN, TLS hostname gốc. Không tải toàn corpus.

| Prefix | SHA-256 (không phải hash toàn corpus) |
|---|---|
| Electronics | `5ff6d1db0f84e0435002eec1eec9e585c1f3d9b5610664c731b7388375d31b98` |
| Cell_Phones_and_Accessories | `0a2341a52e6dbad8d23e4d253306f016ec9a00a4627fa5387bd52dc6d2d6cee1` |

Chọn 75 identity hợp lệ đầu tiên mỗi nguồn: **150/171** dòng được scan, bỏ 21 thiếu
taxonomy. Đây là mẫu phân tầng theo file nguồn, thiên lệch prefix, không ngẫu nhiên
đại diện Amazon. Mapped category: 37 điện tử, 34 phụ kiện điện tử, 74 phụ kiện điện
thoại, 3 laptop, 1 điện thoại, 1 bàn phím; **chưa có tai nghe**.

SQLite `backend/smart_shopping.db`: **150 Product research, 150 provenance,
70 HistoricalPriceReference (USD), 0 ProductOffer của research**. Thiếu giá 80/150.
Tên/category/rating/review count/ảnh: 150/150; brand110/150; model73/150.
Parent ASIN không biến thành SKU. Store không biến thành seller.
Import lần hai: **0 mới / 150 duplicate identities**, không tăng reference.
20/20 record (10 mỗi nguồn, seed2023) đối chiếu name/ID/brand/rating/count/price/hash
với raw gốc pass. Đây là kiểm tra tự động độc lập mapping, không manual labels.

## Kiến trúc và thay đổi

Ba bảng additive trong `backend/app/models/research.py`; nhập streaming ở
`backend/app/services/research/importer.py`; adapter search/matching/ranking ở
`backend/app/services/research/recommendation.py`; API `/api/research/status`,
`POST /api/research/search` tại `backend/app/api/routes/research.py`.

Reuse Product, RequirementData, HardFilter, ScoringEngine matching, Recommendation,
RecommendationSnapshot và API search GET/history/detail/comparison. Live/Demo dedup
loại research IDs để không merge sai. Snapshot không bị runtime mode làm thay đổi.
Không fine-tune mô hình; importer + deterministic recommender không cần API key.

`research-v1`: cơ sở requirements60%, rating25%, reviews5%, historical budget10%;
chuẩn hóa trên thành phần áp dụng. Unknown/unmet không nhận điểm đáp ứng;
priority5 phải matched. Budget VND không so USD; không FX ngầm. Giá luôn là decimal
text trong historical_price, trường offer price=NULL. OfferScore=NULL. Confidence
là completeness, không xác suất tin cậy. Chi tiết [architecture](architecture.md),
[database](database.md).

UI thay ở home/results/card/detail/compare, types/API/utils và `research-notice.tsx`.
Thẻ/chi tiết/so sánh đều cảnh báo lịch sử, attribution, USD/null, không mua hàng,
stock/seller/offer score giả. Demo/Live do server cấu hình; UI không tự bật quyền Live.

Scripts: download/import/verify/benchmark_research; tests research_import,
research_pipeline, research_safety; frontend research.test.mjs, research.spec.ts,
isolated E2E backend loader. Docs/checklist/ignore rules cũng được cập nhật.
Các thay đổi không liên quan có sẵn trong dirty worktree được giữ nguyên.

## Thực nghiệm và kiểm thử

- API thật: “phụ kiện điện thoại dưới 50 USD” → **5** đề xuất;
  “điện tử” → **5**; “điện thoại RAM 999GB” → **0**, không bịa thông số.
  GET snapshot/history/detail/comparison đều đã chạy. Session IDs và evidence:
  [verification.json](research-results/verification.json).
- Full backend cuối **972 passed (91.68s)**. Sau đó bổ sung công cụ nhận nhãn
  ranking: Research suite **40 passed (2.74s)**, gồm6 tests mới; không chạy lại
  full suite vì công cụ độc lập không đổi luồng ứng dụng. Chi tiết [progress](RESEARCH_DATA_PROGRESS.md).
- Frontend48 tests pass; lint/typecheck/build exit0.
- Browser: test đầu15 pass/1 fail do chờ navigation chưa đủ; sửa test chờ URL,
  Research fixture rerun1 pass. Sau đó full **16 passed (42.2s)** với native prefix
  thật cho Research journey trong DB tạm. Không gọi các test fixtures khác là Live.
- `git diff --check` còn trailing whitespace **có sẵn** tại
  `backend/tests/unit/test_oos_recovery.py:19`; không sửa file ngoài scope này.

Benchmark36 queries,12development/24evaluation,3repeats/query:
import150/171, duplicate-generated0/150, USD budget violations0/46,
source-field-support380/380 assertions. Latency evaluate: p50 **49.776ms**,
p95 **75.723ms**, n108. Không bao gồm mạng/HTTP/browser; không là Live crawl success.
[JSON](research-results/benchmark.json), [CSV](research-results/benchmark.csv),
[rubric](RESEARCH_BENCHMARK_RUBRIC.md).

**N/A**: Precision@5, NDCG@5, requirement-match accuracy, semantic explanation
grounding — chưa có human labels độc lập. Không dùng score output làm ground truth.
Đã bổ sung `evaluate_research_labels template/score`: xuất3.600 ô nhãn trống,
kiểm revision/checksum, chỉ tính P@5/NDCG cho query có đủ nhãn. Chạy thực template
trống trả LABELS_PENDING, không sinh metrics giả; xem rubric để tiếp tục gán nhãn.

## Tái lập (PowerShell, từ repository root)

```powershell
cd backend
# Chỉ lần đầu, sau khi đã đọc source assessment và phù hợp phạm vi nghiên cứu:
.venv/Scripts/python.exe -m scripts.download_research_metadata --acknowledge-research-only
# Nếu prefix đã tồn tại, downloader từ chối overwrite: dùng lại sau kiểm checksum.
$researchRevision = '2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e'
foreach ($researchCategory in @('Electronics', 'Cell_Phones_and_Accessories')) {
  .venv/Scripts/python.exe -m scripts.import_research_catalog --input "data/research/meta_$researchCategory.prefix.jsonl" --category $researchCategory --revision $researchRevision --limit 75 --dry-run --report "research-artifacts/dry-$researchCategory.json"
  .venv/Scripts/python.exe -m scripts.import_research_catalog --input "data/research/meta_$researchCategory.prefix.jsonl" --category $researchCategory --revision $researchRevision --limit 75 --report "research-artifacts/import-$researchCategory.json"
  .venv/Scripts/python.exe -m scripts.import_research_catalog --input "data/research/meta_$researchCategory.prefix.jsonl" --category $researchCategory --revision $researchRevision --limit 75 --report "research-artifacts/reimport-$researchCategory.json"
}
.venv/Scripts/python.exe -X utf8 -m scripts.verify_research_catalog
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_research
.venv/Scripts/python.exe -m pytest -q
```

Các lệnh import an toàn idempotent; trên DB đã có dữ liệu, report import mới có0
insert, không dùng overwrite đó để thay số liệu lần nhập đầu trong benchmark.
Benchmark tái lập import success nên dùng DB mới qua `DATABASE_URL` tới file riêng
(không xóa DB cũ) và output report riêng. Verification tạo ba session test có ghi
snapshot/history trong DB đang chọn; không sửa Product/price.

```powershell
cd ../frontend
npm.cmd test
npm.cmd run lint
$env:RESEARCH_E2E_DATA = (Resolve-Path '../backend/data/research').Path
npm.cmd run test:e2e
Remove-Item Env:RESEARCH_E2E_DATA
npm.cmd run build
```

Backend chạy từ `backend/`: `.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`;
frontend `npm.cmd run dev`; chọn Research Catalog ở trang chủ.

## Còn lại

1. Nhãn độc lập cho evaluation split, tính Precision/NDCG/accuracy rồi đánh giá
   chất lượng thật; R08 còn PARTIAL.
2. Mẫu thiếu đại diện (ít điện thoại/laptop, không tai nghe), parser local giới hạn;
   không suy rộng kết quả benchmark thành chất lượng mọi nhu cầu tiếng Việt.
3. Quyền nghiên cứu không là quyền thương mại/tái phân phối; phải rà soát nếu đổi scope.
4. Blocker quyền nguồn Live/browser crawler trước đó không được giải quyết bằng dataset;
   trạng thái crawler không thay đổi. Không biến giá2023 thành giá hiện hành.
