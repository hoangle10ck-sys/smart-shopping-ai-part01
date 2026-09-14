# Architecture

Tài liệu mô tả implementation sau Phase 7. PROJECT OVERRIDES trong MASTER_SPEC
ưu tiên tên/route đang hoạt động, không yêu cầu dựng lại repository theo cây mẫu.

## Luồng chính

```mermaid
flowchart TD
  User[USER: nhập nhu cầu] --> UI[Next.js Home]
  UI --> Analyze[FastAPI Requirement Analysis]
  Analyze --> Missing{Thiếu category/budget/purpose?}
  Missing -->|Có| Clarify[Clarification: nhận câu trả lời và phân tích lại]
  Clarify --> Analyze
  Missing -->|Không| Query[Python Query Generator]
  Query --> Cache{Live session mới có cache hợp lệ?}
  Cache -->|Có| Copy[Copy complete snapshot]
  Cache -->|Không| Search[Mock Demo hoặc Tavily Live]
  Search --> Extract[Source filtering / Extraction]
  Extract --> Normalize[Normalization]
  Normalize --> Dedup[Dedup: Product và Product Offer]
  Dedup --> Filter[Hard Filter]
  Filter --> Score[Python Scoring / Requirement Matching]
  Score --> Rank[Ranking Top K]
  Rank --> Evidence[Confidence / Structured Evidence]
  Evidence --> Explain[Demo / LLM / Fallback Explanation]
  Explain --> Snapshot[(Recommendation Snapshot)]
  Copy --> Snapshot
  Snapshot --> Results[Next.js Results / filter / detail / compare / feedback]
  Snapshot --> History[History]
  History --> Results
```

## Phân chia trách nhiệm

| Công việc | Thành phần thực thi |
|---|---|
| Hiểu nhu cầu ngôn ngữ tự nhiên | `services/llm/client.py`: local MockLLMClient hoặc OpenAI/Gemini; Pydantic kiểm tra structured output |
| Clarification | `RequirementAnalyzer` xác định dữ liệu thiếu, route ghép câu trả lời vào ngữ cảnh rồi phân tích lại |
| Query generation | `services/llm/query_generator.py` là Python deterministic dù nằm trong thư mục `llm` |
| Search | `SearchProvider` interface, MockSearchProvider/TavilySearchProvider, SourceStrategy/SourceFilter |
| Extraction | Parser deterministic hỗ trợ labelled Demo payload và các mẫu search text; chưa có extraction LLM tổng quát |
| Normalize/dedup | Python parsers và ProductDeduplicator; category chỉ dựa evidence sản phẩm |
| Hard filter, scoring, rank, matching | Python; LLM không được quyết định final score |
| Evidence/confidence | Python; provenance chỉ khi observation khớp field value của candidate |
| Giải thích | LLM chỉ tạo narrative có schema; Demo hoặc lỗi provider dùng deterministic explanation |
| Comparison | Python xếp theo score/rating/review count; không có cuộc gọi LLM comparison |
| Frontend | Render backend response, filter/sort trong snapshot, không chấm lại điểm hoặc suy diễn requirement/evidence |

Analyzer Live thử provider chính, provider dự phòng (nếu cấu hình được), cuối cùng
parser local. Explanation có chuỗi provider riêng với `generation_mode` là
`demo`, `openai`, `gemini`, `fallback`. Search Live không chuyển sang mock âm thầm.

## Điểm số

```text
Final = budget*0.25 + requirement*0.30 + purpose*0.20
      + rating*0.10 + review_count*0.05 + source*0.10
```

Điểm thành phần gốc và final đều chuẩn hóa 0–100. UI hiển thị điểm gốc cùng trọng
số; không phải điểm contribution đã nhân trọng số trong ví dụ schema gốc của SPEC.
Requirement score tính tỷ lệ tổng priority của tiêu chí matched; unknown/unmet
đều không được cộng điểm nhưng UI phân biệt. Không có explicit requirements thì
requirement score là 100 và matching rỗng, không tự thêm RAM/microphone từ purpose.
RAM/storage dùng so sánh capacity/value, alias và đơn vị; các tiêu chí định tính
có rubric bảo thủ. Purpose score vẫn là heuristic từ evidence text/aliases, không
phải benchmark hiệu năng thực tế.

Data Confidence tách khỏi AI Match: source reliability 30%, product completeness
25%, offer completeness 20%, consistency 15%, corroboration 10%. Freshness được
ghi thời điểm nhưng chưa có time-decay term riêng trong công thức confidence.

## Dữ liệu và tính nhất quán

- Product là catalog hợp nhất. Offer giữ merchant/giá/URL/availability/thời điểm.
  Dedup điền specifications còn thiếu, không tự ghi đè mọi field khi có nguồn mới.
- Một run thành công ghi recommendation rows và toàn bộ snapshot JSON trong cùng
  transaction. `total_found` là candidates, `total_filtered` là số qua lọc,
  `total_recommended` là số cuối sau Top K, kể cả trường hợp kết quả rỗng.
- GET session/recommendation dùng snapshot; `data_mode` là provenance đã lưu,
  `demo_mode` trong search response là cấu hình runtime. Không dùng runtime mode
  để đoán lịch sử.
- Legacy không có snapshot dùng phép tính lại đồng bộ, chỉ đọc, không gọi external
  LLM và gắn `legacy_recomputed`; chưa có kết quả là `not_generated`.
- `requirement_matches` và `evidence.fields` là JSON snapshot, snapshot cũ mặc định
  rỗng. Không truy catalog để bổ sung evidence cho snapshot đã tồn tại.
- Product detail hiển thị catalog hiện có, có thể khác giá session. Comparison mới
  lấy dữ liệu từ cùng recommendation view, lưu riêng JSON result và `data_semantics`.
  Ưu/nhược điểm lấy từ why_fit/tradeoffs đã lưu. Comparison cũ không được backfill.

## Cache, History và lỗi

Cache SQLite qua abstraction `SearchCache`, key SHA-256 của normalized requirement
và config ảnh hưởng pipeline. TTL mặc định 1800 giây. Chỉ session Live mới, chưa có
kết quả, mới dùng cache; Demo vẫn chạy pipeline offline. Cache hit sao chép snapshot
và metadata, không sửa shared Product/Offer; cảnh báo nêu rõ cache và thời gian nguồn.
Key còn hợp lệ phải tham chiếu đúng snapshot của session nguồn COMPLETED. Rerun
session thành công bỏ qua cache để refresh. Xem [Phase 4 notes](PHASE4_NOTES.md).

Lỗi một query/source cho phép tiếp tục phần còn lại và lưu warnings. Khi tất cả
query provider thất bại, search không xóa raw/recommendation/snapshot cũ; HTTP 503,
status FAILED và warning được giữ khi GET. Session mới có thể dùng cache hợp lệ
được tìm thấy sau lỗi; nếu không có thì báo lỗi. LLM lỗi không làm pipeline mất
khả năng trả recommendation deterministic.

History đọc SearchSession + snapshot, không có bảng history riêng và không gọi
provider. MVP local dùng chung dữ liệu, chưa triển khai đăng nhập, phân quyền,
rate limiting hay theo dõi người dùng cá nhân.

## Runtime

Local: Next 3000, FastAPI 8000, SQLite tạo bảng qua lifespan. CORS cho hai origin
localhost/127.0.0.1:3000. Docker giữ các port này, có backend healthcheck, SQLite
named volume và process không phải root. Frontend gọi backend qua URL public đã
nhúng lúc build, không qua Docker hostname trong browser.

Browser E2E dùng server riêng 13000/18000, SQLite tạm, Demo và network guard.
Docker hiện **NOT RUNTIME VERIFIED** trên máy thực hiện Phase 7.

Repository truy cập ORM hiện nằm ở routes/services; không refactor chỉ để khớp
tên thư mục trong SPEC. Logging có ở một số provider/routes, chưa có đầy đủ
request_id và latency theo mọi stage; tiến độ UI là trạng thái thực, không phải
realtime telemetry từng bước. Các giới hạn được ghi ở [final audit](FINAL_AUDIT.md).
