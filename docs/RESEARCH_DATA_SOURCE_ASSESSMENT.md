# R00 — Amazon Reviews 2023, đánh giá nguồn

Ngày kiểm tra: 2026-10-17. Phạm vi: đồ án nghiên cứu phi thương mại, metadata
được lưu cục bộ; không tái phân phối raw dataset/database, không mục đích bán hàng.

## Quyền và giới hạn

- [Dataset chính thức](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023).
- [Schema native JSONL](https://amazon-reviews-2023.github.io/data_loading/jsonl.html).
- [Trao đổi quyền sử dụng](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/discussions/1):
  nhóm xuất bản nói không thể cấp giấy phép cho toàn bộ dataset (2024-03-08),
  và không phản đối sử dụng cho luận văn trong trao đổi 2024-12-08.
  Đây **không phải giấy phép mở hoặc quyền tái phân phối**.
- Quyết định: tiếp tục mẫu nhỏ cục bộ cho phạm vi nghiên cứu người dùng đã chọn;
  thay đổi sang thương mại/phân phối cần rà soát quyền riêng. Không đảm bảo pháp lý.
- Citation: Hou et al. (2024), *Bridging Language and Items for Retrieval and
  Recommendation*, https://arxiv.org/abs/2403.03952.

## Bằng chứng khảo sát thực

HF API trả revision `2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e`.
HEAD metadata Electronics: HTTP 200, 5,246,144,134 bytes. GET Range
`bytes=0-16383`: HTTP 206, đúng 16,384 bytes. Không tải toàn bộ archive.
URL pin: `https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e/raw/meta_categories/meta_Electronics.jsonl`.
Record đầu `B00MCW7G9M`: title string, price=null, images=list[dict],
features/description/categories=list, details=dict, store string.

## Mapping

| Native | Catalog | Giới hạn |
|---|---|---|
| parent_asin | external_product_id | parent group, không phải SKU/variant |
| title/main_category/categories | name/category + provenance taxonomy | không gán phụ kiện thành điện thoại |
| details | specifications | chỉ scalar có sẵn; brand/model chỉ từ key rõ ràng |
| average_rating/rating_number | rating/review_count | lịch sử, không là seller trust |
| images | image_url | chỉ URL HTTPS Amazon media được cho phép |
| features/description/store | provenance JSON | store không phải merchant đang bán |
| price | historical_price_references | USD theo schema chính thức, null/invalid => không có reference |

`reference_year=2023`, `price_observed_at=NULL`; imported_at không là thời điểm
quan sát giá. Identity = dataset + revision + parent_asin. Hash input prefix và
hash từng dòng được giữ riêng, không gọi hash prefix là hash toàn corpus.

## Khảo sát kiến trúc / thay đổi tối thiểu

Worktree có nhiều thay đổi crawler/UI từ trước; giữ nguyên. Product dùng chung,
thêm bảng provenance/reference/import log. CandidateBuilder cũ bắt đầu từ offers
và RawProductCandidate nên cần research adapter riêng, không dựng offer/raw giả.
Tái sử dụng RequirementData, ScoringEngine requirement matcher, HardFilter,
Recommendation/RecommendationSnapshot, API GET/history/comparison và UI results.
Research search chỉ SQLite, không đi CachedSearchService/Tavily/LLM/crawler.
Không sửa trạng thái T02/T05/T09; live flags không đổi.

Mẫu: prefix có giới hạn từ hai file metadata chính thức; lấy tối đa 75 identity
hợp lệ mỗi file (150 tổng). Đây là stratification theo nguồn category, có prefix
bias, không đại diện ngẫu nhiên cho Amazon. Benchmark phải công bố giới hạn này.
