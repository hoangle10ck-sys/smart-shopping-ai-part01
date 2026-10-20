# R08 — Rubric và split đánh giá

## Cập nhật sau audit 2026-10-17

Catalog mới: **191 sản phẩm**,6 điện thoại,20 laptop,19 tai nghe; mẫu vẫn thiên lệch
prefix, không đại diện thị trường. Báo cáo baseline150 phía dưới giữ để đối chiếu.
Benchmark mới trong `docs/research-results/expanded/`: 42 queries (18 development,
24 evaluation),126 lượt đo. Sáu case C01–C06 là regression grammar do agent viết,
không phải human relevance labels. Không thay đổi evaluation split hay chỉnh weights.
Kiểm tra ngân sách gồm cả cận dưới/cận trên; case mới dùng expected bounds độc lập
với parser. Các query cũ kiểm tra constraints đã parse, không đo độ chính xác NLP.
Import success phân biệt với selection yield: quota chủ ý bỏ qua phụ kiện không
phải lỗi persistence. Nguồn gốc từng identity/hash được đóng băng trong report.

Template mới: `backend/research-artifacts/expanded-relevance-labels.csv`, **4.584**
ô trống (24 × 191). Không ghi đè template150 cũ. Vẫn **LABELS_PENDING**; không có
người đánh giá độc lập nên P@5/NDCG@5/requirement accuracy/semantic grounding N/A.

```powershell
# backend/, sau khi chạy verification và benchmark cho cohort mới
.venv/Scripts/python.exe -m scripts.evaluate_research_labels template --benchmark ../docs/research-results/expanded/benchmark.json --labels research-artifacts/expanded-relevance-labels.csv
.venv/Scripts/python.exe -m scripts.evaluate_research_labels score --benchmark ../docs/research-results/expanded/benchmark.json --labels research-artifacts/expanded-relevance-labels.csv --output ../docs/research-results/expanded/human-ranking.json
```

Template từ chối ghi đè. Sau khi người đánh giá điền nhãn, chỉ chạy lại `score`.

## Baseline ban đầu

36 truy vấn tại `backend/benchmarks/research_queries.csv`: 12 development,
24 evaluation. Tác giả bộ query: coding agent; **chưa có ground truth do người
đánh giá độc lập gán nhãn**. Không gọi các query/rubric này là nhãn thủ công đã có.

## Quy trình gán nhãn (còn cần người đánh giá)

Đóng băng revision/checksum catalog và công thức research-v1 trước khi đánh giá.
Người đánh giá xem metadata gốc, không xem thứ hạng/điểm hệ thống. Gán mỗi cặp
query–parent_asin: 0 không liên quan/vi phạm, 1 liên quan nhưng thiếu thông số,
2 phù hợp danh mục và tiêu chí đã biết, 3 đáp ứng đầy đủ mọi ràng buộc có chứng cứ.
Ghi unknown riêng cho giá/thông số thiếu; ngân sách VND không quy đổi USD.
Phân biệt điện thoại với ốp/cáp; parent_asin không xác nhận variant/SKU.
Với từng requirement ghi matched/unmet/unknown kèm JSON field/quote.
Hai người gán nhãn độc lập, hòa giải bất đồng và ghi reviewer/date.

CSV nhãn cần có: query_id,parent_asin,relevance,reviewer,evidence,adjudication.
Không dùng output của chính scoring engine làm ground truth. Evaluation split
không dùng điều chỉnh trọng số sau khi có nhãn.

## Metrics

- Import success: imported / scanned (có skip taxonomy).
- Completeness: count trường không NULL / imported (không đo chính xác ngữ nghĩa).
- Duplicate generated: tăng Product ở lần nhập hai / selected identities.
- USD budget violations: đề xuất vi phạm giới hạn USD / đề xuất có USD constraint.
- p50/p95: thời gian evaluate SQLite+rank, 36 truy vấn × 3 lượt, không bao gồm HTTP/UI.
- Source field support: name/rating/count/price trong kết quả khớp JSONL gốc /
  số assertions kiểm tra; đây là kiểm tra tự động, **không phải đánh giá con người
  về tính đúng của mọi câu giải thích**.
- Precision@5, NDCG@5, requirement-match accuracy và semantic explanation
  grounding: **N/A — thiếu independent human labels**. Không thay bằng fixture.

Sample prefix có 1 điện thoại, 3 laptop, không tai nghe trong lần nhập hiện tại;
kết quả rỗng là hợp lệ, không bịa để đủ K. Mẫu 150 này không đại diện toàn thị trường.

## Công cụ gán nhãn và tính ranking metrics

Từ `backend/`:

```powershell
.venv/Scripts/python.exe -m scripts.evaluate_research_labels template
# Người đánh giá điền research-artifacts/relevance-labels.csv theo rubric phía trên.
.venv/Scripts/python.exe -m scripts.evaluate_research_labels score
```

Template đã được xuất cục bộ: 3.600 ô trống (24 evaluation queries × 150 sản phẩm),
không kèm score/rank của hệ thống. Có query, parent_asin, nguồn, dòng JSONL,
revision/checksum để đối chiếu metadata. Lệnh template từ chối ghi đè file có sẵn.
Nhãn hoàn chỉnh cần relevance 0..3, reviewer, reviewed_at, evidence, adjudication.
Phần mềm kiểm tra định dạng/provenance; không thể tự chứng nhận người gán nhãn độc lập.

Chỉ query đã gán nhãn toàn catalog được tính, tránh coi bản ghi chưa chấm là không
liên quan. Precision@5 dùng relevance≥2, mẫu số cố định5 kể cả trả ít kết quả.
NDCG dùng gain `2^relevance-1`, log2 discount; query không có ideal gain để N/A riêng.
Development split bị loại khỏi phép đo. Báo cáo lưu riêng tại
`backend/research-artifacts/human-ranking.json`, không ghi đè benchmark gốc.

Chạy thực với template trống: **LABELS_PENDING**, 0 judgments, cả hai metric NULL.
Requirement-match accuracy/semantic explanation grounding vẫn cần nhãn chuyên biệt
và chưa được công cụ ranking này đo.
