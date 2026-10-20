# PROMPT CHO CODEX — TRIỂN KHAI MỤC TIÊU A: RESEARCH PRODUCT CATALOG

Bạn đang làm việc trên repository `ThinhLoLem/smart-shopping-ai-part01`. Hãy đọc `TASKS_RESEARCH_DATA.md` và thực thi tuần tự R00–R09, trực tiếp chỉnh code, chạy tests, cập nhật checkpoint sau mỗi pha. Không chỉ viết kế hoạch.

## Mục tiêu cụ thể

Chuyển đồ án Smart Shopping AI từ tình trạng chưa có sản phẩm thật sang có catalog **100–200 sản phẩm điện tử thật được nhập từ bộ dữ liệu nghiên cứu**, đủ để AI phân tích nhu cầu tiếng Việt, tìm kiếm catalog, so sánh đặc tính, tính ProductSuitabilityScore và giải thích. Đây là **MỤC TIÊU A — HISTORICAL_RESEARCH**, không phải crawling giá bán Live và không thay thế các blocker T02/T05/T09 của crawler hiện tại.

## Dữ liệu cần ưu tiên

- Amazon Reviews 2023 của McAuley Lab: chỉ item metadata của `Electronics` và `Cell_Phones_and_Accessories` (có thể khảo sát `Computers` nếu bộ dữ liệu có category phù hợp; không đoán). Nguồn: https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023 ; schema native: https://amazon-reviews-2023.github.io/data_loading/jsonl.html .
- Chính sách sử dụng: https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1 . Nhóm xuất bản không tự cấp được giấy phép cho mọi nội dung; có bình luận ủng hộ dùng cho luận văn phi thương mại, KHÔNG đồng nghĩa quyền tái phân phối vô điều kiện. Hãy đánh giá quyền trước khi tải/sử dụng và không commit dữ liệu thô nếu quyền chưa rõ.
- Fallback khi không đủ cơ sở sử dụng: Amazon Berkeley Objects https://amazon-berkeley-objects.s3.amazonaws.com/index.html (CC BY 4.0, attribution required); catalog thật, **không có giá bán đáng tin để sử dụng**. Nếu fallback, tập trung so sánh thông số mà không có giá.

## Ràng buộc kỹ thuật phải giữ

1. Audit code hiện hữu trước; Product/ProductOffer/Source/RawProductCandidate/ScoringEngine/RecommendationService/snapshot đã tồn tại. Không viết lại các module ổn định và không ghi đè mã đang sửa cục bộ.
2. Import file JSONL/JSONL.gz local bằng parser streaming `json.loads`, không `eval`, không `trust_remote_code=True`, không tải toàn bộ corpus vào RAM. Giới hạn kích thước, số record; report input SHA-256, source/version, imported/skipped/errors.
3. Mapping dựa vào metadata gốc, ví dụ `parent_asin`, `title`, `main_category`, `description`, `features`, `details`, `price`, `average_rating`, `rating_number`, `images`, `store`. Price có thể `null` hoặc chuỗi `None`. Không biến `store` thành verified merchant/seller; không đoán RAM, SKU hoặc các đặc tính không có.
4. Lưu product identity bằng `(dataset_id, dataset_revision, parent_asin)` và bằng chứng từng field. Xử lý variants chỉ khi có thông tin; parent_asin không phải SKU.
5. Giá là **tham khảo lịch sử**, không phải giá bán hiện tại. Lưu dưới dạng historical reference riêng, không tạo `ProductOffer` đang có thể mua chỉ để thỏa bảng cũ. `imported_at` KHÔNG được dùng làm `price_observed_at`; nếu không có ngày chính xác, để `NULL`, ghi năm nguồn 2023. Không sử dụng giá USD như VND và không dùng tỷ giá tự bịa.
6. Research Mode tìm catalog SQLite có sẵn, không kích hoạt crawl hay tạo `LIVE_VERIFIED`; hard filter/score bảo toàn semantic matched/unmet/unknown, no seller score, no buy-now. Recommendation phải chạy thật trên dữ liệu đã nhập và có snapshot/history.
7. Giao diện ghi nổi bật `Dữ liệu nghiên cứu/lịch sử, không phản ánh giá đang bán`, có `Nguồn dữ liệu`, không có `Mua ngay` khi không có seller hợp lệ. Explanation không bịa ưu/nhược điểm, không tự cho điểm.
8. Tests offline (fixtures chỉ dùng test; không báo là Live) + integration DB + frontend regressions; import dataset thật chỉ khi có quyền và môi trường thực sự có file.
9. Cập nhật `docs/RESEARCH_DATA_PROGRESS.md`, `docs/RESEARCH_DATA_INTEGRATION_REPORT.md`, README và file tasks nghiên cứu, không ghi đè trạng thái T02/T05/T09 của crawler Live.

## Thứ tự ưu tiên

- P0: R00 quyền/đánh giá nguồn, R01 mapping/schema, R02 importer, R03 DB idempotency, R04 research recommendation, R06 tests, R07 import thật.
- P1: R05 frontend, R08 benchmark, R09 docs/final audit.
- Nếu dataset Live download bị giới hạn mạng hoặc quyền: hoàn thành các phần offline an toàn, ghi BLOCKED_RIGHTS/BLOCKED_DATA chính xác, không tạo sản phẩm giả rồi báo hoàn thành.

## Báo cáo cuối bằng tiếng Việt

A. File thay đổi, schema/migrations và công thức scoring.
B. Dataset nguồn, phạm vi quyền, version/revision, checksum và cách tải (không tiết lộ credential).
C. Số sản phẩm thật nhập thành công, số có giá lịch sử, số không có giá, các category, số duplicate/skipped.
D. Các lệnh chạy importer 2 lần và so sánh số dòng.
E. Ba luồng end-to-end: điện thoại/phụ kiện, thiết bị điện tử, một query không đủ bằng chứng.
F. Tests đã chạy: pass/fail/not run, không suy đoán.
G. Benchmark với numerator/denominator; ghi N/A khi chưa đo.
H. Trạng thái `RESEARCH_DATASET_VERIFIED` tách biệt `LIVE_VERIFIED` và các blocker crawler còn lại.

**BẮT ĐẦU:** kiểm tra `git status`, đọc repo và TASKS_RESEARCH_DATA.md, sau đó thực thi pha R00 ngay. Không push/force push.
