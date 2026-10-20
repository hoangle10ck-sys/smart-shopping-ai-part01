# Công việc crawler còn lại

Cập nhật: 2026-10-16 (Asia/Saigon)

T02 (DNS rebinding) và T05 (Crawl4AI runtime) đã hoàn thành, có test và bằng
chứng runtime trong `docs/CRAWLER_PROGRESS.md`. Các việc chưa thể hoàn thành chỉ
còn phụ thuộc nguồn sản phẩm Live:

## 1. Nguồn sản phẩm điện tử được phép — BLOCKED_SOURCE_PERMISSION

- Chưa có merchant nào được phê duyệt trong `COLLECTOR_SOURCE_REGISTRY_JSON`.
- Cần domain, `allowed_paths`, terms URL, robots URL, ngày kiểm tra và căn cứ
  cho phép thu thập/tái sử dụng dữ liệu.
- WooCommerce Store API là API storefront công khai, nhưng quyền của từng
  merchant vẫn phải được xác minh riêng.
- Best Buy không được bật: cần API key và điều khoản đã rà soát không phù hợp
  cho mục đích phân tích/so sánh giá vì lợi ích bên thứ ba.
- Hai cờ `COLLECTOR_LIVE_ENABLED` và `COLLECTOR_POLICY_CONFIRMED` tiếp tục tắt.

## 2. Live ingestion và idempotency — LIVE_NOT_VERIFIED

Sau khi mục 1 được giải quyết:

1. Chạy preflight cho nguồn đã đăng ký.
2. Ingest tối đa 5 sản phẩm / 2 trang.
3. Xác minh name, price, currency, SKU/variant, URL và `observed_at`.
4. Kiểm tra Product, Variant, Offer, PriceObservation và evidence trong SQLite.
5. Chạy lần hai và chứng minh số Product/Variant/Offer không tăng do duplicate.
6. Xác nhận Recommendation Engine đọc được bản ghi Live.

Hiện tại: URL sản phẩm Live 0; Product 0; Variant 0; Offer 0;
PriceObservation 0. Không dùng mock/fixture để thay thế.

## 3. Benchmark Live — N/A

Chỉ thực hiện sau khi có nguồn ở mục 1: lập URL dataset và ground truth độc lập,
đo fetch/extraction/price evidence/SKU/completeness/latency/persistence/dedup;
so sánh HTTPX, Crawl4AI và Crawl4AI+LLM khi cả ba chế độ đều được phép.
