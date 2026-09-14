# API

Base URL local: `http://127.0.0.1:8000`. JSON UTF-8. Contract lấy từ routes/schemas
hiện có, không đổi `/api/comparisons` thành `/api/compare` theo ví dụ SPEC cũ.
Swagger `/docs` và `/openapi.json` là nguồn schema máy đọc tại runtime.

## Toàn bộ application routes

| Method | Path | Request / Response và lỗi chính |
|---|---|---|
| GET | `/` | Thông tin backend và đường dẫn docs/health |
| GET | `/api/health` | 200: liveness `status`, `service`, không gọi external API |
| GET | `/api/system/status` | 200: status/environment/database/demo_mode; 503 nếu DB không khả dụng |
| POST | `/api/requirements/analyze` | raw_query → session_id, requirement, needs_clarification, missing_fields, clarification_question, search_queries |
| POST | `/api/requirements/clarify` | session_id, answer → analysis response mới; 404 nếu thiếu session/requirement |
| POST | `/api/search` | session_id → SearchPipelineResponse; 404 session thiếu, 409 chưa có query, 503 provider thất bại toàn bộ, 500 lỗi pipeline khác |
| GET | `/api/search/{session_id}` | Result đã lưu + trạng thái/warnings; 404 session không tồn tại |
| GET | `/api/recommendations/session/{session_id}` | session_id, data_semantics, total, items; 404/409 khi session/view không hợp lệ |
| GET | `/api/recommendations/{recommendation_id}` | id/session_id/product_id/rank/data_semantics/item; 404 ID không tồn tại, 409 không khớp view |
| GET | `/api/products/{product_id}` | Catalog Product hiện có + tất cả offers và source metadata; 404 nếu không có |
| POST | `/api/comparisons` | session_id, product_ids (2–3) → 201 ComparisonResponse; 404 session/product thiếu, 409 không thuộc recommendation/view nhất quán |
| GET | `/api/comparisons/{comparison_id}` | ComparisonResponse đã lưu; 404 nếu không có |
| POST | `/api/feedback` | session_id, optional product_id, is_helpful, optional reason/comment → 201 FeedbackResponse; 404/409 cho tham chiếu không hợp lệ |
| GET | `/api/feedback/session/{session_id}` | session_id, total, items; 404 session không có |
| GET | `/api/history` | Query limit=50 (1–100), offset=0 (>=0) → items/total/limit/offset, mới nhất trước |
| GET | `/api/history/{session_id}` | Metadata HistoryItem + result (nullable); 404 session thiếu |

FastAPI còn cung cấp GET `/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`.
Các request vi phạm schema trả 422. Validation errors có `detail` là array;
business errors thường là string, một số comparison/feedback errors là object.
MVP chưa có authentication: các API/History là dữ liệu dùng chung trong instance
local. Không public instance như hệ thống đa người dùng đã có phân quyền.

## Analysis và clarification

```json
{"raw_query":"Tôi có 500 nghìn, cần tai nghe để học online, mic tốt, pin lâu."}
```

`raw_query`: 3–2000 ký tự. Requirement gồm category (nullable), budget_min/max
(nullable, >=0, min<=max), currency, purpose[], brands[], requirements[],
excluded_requirements[], sort_preference và confidence 0–1.
Mỗi requirement item có name/value/priority 1–5. Đây là requirement được phân tích,
không phải category/evidence của sản phẩm.

Nếu `needs_clarification=true`, chưa search. Gửi:

```json
{"session_id":"<UUID từ analyze>","answer":"Ngân sách 15 triệu, dùng học lập trình."}
```

Answer 1–1000 ký tự. Backend ghép với raw query, phân tích lại và tạo queries nếu
đủ thông tin. Frontend dùng cùng session ID để tiếp tục.

## Search và recommendation

```json
{"session_id":"<UUID từ analyze/clarify>"}
```

SearchPipelineResponse có:

- `session_id`, `status`: PENDING/PROCESSING/COMPLETED/FAILED.
- `queries`, `sources`, `raw_products`, total_results/total_sources/total_products
  mô tả search/extraction, khác bộ đếm candidates sau chuẩn hóa.
- `requirement`, `candidates`, `filter_decisions`, `recommendations`.
- `total_found`: số candidate; `total_filtered`: số **qua lọc**, không phải số bị
  loại; `total_recommended`: số sau Top K. Luôn recommended <= filtered <= found.
- `warnings`, `processing_time_ms`.
- `data_semantics`: `snapshot`, `legacy_recomputed`, `not_generated`.
- `data_mode`: `demo`, `live` hoặc null ở dữ liệu cũ; `demo_mode`: cấu hình runtime.

RecommendationItem gồm product_id/rank/name, category/brand/model/image_url,
price/currency/merchant/product_url/availability/last_checked_at, rating/review_count,
specifications, score, confidence, requirement_matches, evidence và explanation.
`score` chứa final_score và budget_score/requirement_score/purpose_score/rating_score/
review_score/source_score; tất cả là điểm 0–100 chưa nhân trọng số component.

Ví dụ cấu trúc matching (minh họa contract, không phải dữ liệu shop):

```json
{
  "name": "ram",
  "requested_value": "16GB",
  "product_value": "8GB",
  "status": "unmet",
  "reason": "Giá trị đã biết không đáp ứng yêu cầu."
}
```

`status` chỉ matched/unmet/unknown; product_value nullable. Không có explicit
requirements thì array rỗng. `EvidenceReport` có confidence/breakdown/source_count/
offer_count, supporting_evidence[], warnings[] và fields[]. Field evidence gồm
field, value, nullable source/domain/merchant/url/retrieved_at/reliability.
Thông số dùng path `specifications.ram`, v.v. Không có observation phù hợp thì
không có entry, không gắn nguồn từ candidate khác hoặc session khác.

Explanation có summary, why_fit[], tradeoffs[], evidence_notes[], generation_mode
demo/openai/gemini/fallback. Narrative không được dùng làm final score hoặc làm
nguồn phân loại matched/unmet/unknown.

GET snapshot không thu thập dữ liệu mới. Provider thất bại khi rerun trả 503;
GET vẫn có thể trả 200 với `status=FAILED`, warnings và snapshot thành công cũ.
Đây không phải search mới thành công. Empty recommendations khi search thành công
khác với provider error. Nguồn `sources` cấp search là bản ghi tổng hợp; provenance
của recommendation lịch sử phải đọc `recommendations[].evidence.fields` đã snapshot.

## Product detail và comparison

Product detail là catalog hiện có: id/name/category/brand/model, rating/review_count,
specifications/pros/cons, timestamps và offers[]. Offer có id/merchant/price/currency/
availability/source_id/source_domain/source_title/source_reliability_score/
product_url/last_checked_at. Không coi giá detail là giá của session cũ.

```json
{"session_id":"<UUID>","product_ids":[1,2]}
```

IDs phải dương, không trùng, 2–3 sản phẩm thuộc recommendation của session.
ComparisonResponse gồm id/session_id/product_ids/result/created_at. Result có
winner_product_id, summary, criteria, products và (comparison mới từ Phase 7)
`data_semantics`. Giá/rating/specifications/score của comparison mới lấy từ cùng
recommendation view; legacy không có snapshot được tính lại đồng bộ chỉ đọc.
Pros/cons lấy từ explanation why_fit/tradeoffs của view, không lấy field catalog
đã thay đổi. Winner chọn deterministic: score, rồi rating, rồi review count.
Không gọi LLM cho comparison. GET trả JSON đã lưu; comparison cũ không backfill,
có thể chưa có data_semantics. Giữ nguyên các key response cũ.

## Feedback và History

```json
{"session_id":"<UUID>","product_id":1,"is_helpful":false,"reason":"Giá cao","comment":"Tôi muốn rẻ hơn."}
```

Reason tối đa 120, comment tối đa 2000 ký tự; blank được chuẩn hóa null. Phản hồi
được lưu, chưa tự học hoặc điều chỉnh weights. Product_id có thể null cho phản hồi
session. List feedback trả items theo API hiện tại.

HistoryItem có session_id/raw_query/status/created_at/completed_at/recommendation_count.
Detail thêm `result: SearchPipelineResponse | null`; null khi session thiếu
requirement. History đọc dữ liệu có sẵn, không gọi provider hoặc tự rerun search.

## Thử nhanh

Mở `/docs`: analyze → lấy session_id → search → GET search → chọn hai product_id
trong recommendations → POST comparisons → feedback → history. Dùng Demo với
API keys rỗng; [demo.md](demo.md) có dữ liệu/điểm quan sát cho ba câu nhập chính.
