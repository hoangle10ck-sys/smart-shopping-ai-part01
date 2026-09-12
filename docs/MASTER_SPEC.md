# MASTER_SPEC.md — SMART SHOPPING AI

> **Mục đích của file này:** dùng làm specification để Codex/IDE **audit, hoàn thiện và sửa có kiểm soát** project hiện tại `smart-shopping-ai-part01`.
>
> **QUY TẮC ƯU TIÊN:** phần **PROJECT OVERRIDES** bên dưới có độ ưu tiên cao hơn mọi câu chữ xung đột trong phần specification gốc.

## PROJECT OVERRIDES — ÁP DỤNG CHO PROJECT HIỆN TẠI

### 1. Trạng thái project

Project `smart-shopping-ai-part01` **đã được phát triển và đang có code hoạt động**.

Codex phải:

- Đọc code hiện tại trước khi đưa ra kết luận.
- Không xây lại project từ đầu.
- Không tạo một project mới bên cạnh project hiện tại.
- Không đổi tên thư mục gốc `smart-shopping-ai-part01`.
- Không xóa hoặc thay thế chức năng đang hoạt động chỉ để làm cấu trúc giống tài liệu.
- Ưu tiên tương thích ngược với backend, frontend, database và tests hiện có.
- Chỉ sửa những phần thật sự lỗi, thiếu hoặc xung đột với mục tiêu hệ thống.

### 2. Quy trình bắt buộc trước khi sửa

Trước khi chỉnh sửa code, Codex phải:

1. Đọc cấu trúc backend và frontend.
2. Đọc API routes hiện tại.
3. Đọc models, schemas, services, repositories và configuration.
4. Đọc toàn bộ tests hiện có.
5. So sánh implementation hiện tại với specification này.
6. Phân loại từng mục quan trọng thành:
   - `PASS`
   - `PARTIAL`
   - `MISSING`
   - `CONFLICT`
7. Chạy backend tests hiện tại.
8. Chạy frontend build.
9. Nếu có lint script thì chạy lint.
10. Báo cáo các lỗi thật sự trước khi sửa.

### 3. Không được sửa chỉ để khớp tên trong specification

Specification gốc được viết ban đầu theo hướng xây hệ thống từ đầu. Với project hiện tại:

- Tên file, thư mục hoặc route có thể khác nhưng vẫn hợp lệ nếu chức năng tương đương.
- Không đổi API đang được frontend/tests sử dụng nếu không có lý do kỹ thuật rõ ràng.
- Không đổi database schema nếu việc đó có nguy cơ phá dữ liệu hiện tại.
- Không nâng dependency chỉ để làm mới version nếu project đang chạy ổn.
- Không xóa test để làm test pass.

### 4. API hiện tại cần được bảo toàn

Khi audit, đặc biệt ưu tiên bảo toàn các API đang được project sử dụng, bao gồm:

```text
GET  /api/health
GET  /api/system/status

POST /api/requirements/analyze
POST /api/requirements/clarify

POST /api/search
GET  /api/search/{session_id}

GET  /api/products/{product_id}

POST /api/comparisons
GET  /api/comparisons/{comparison_id}

POST /api/feedback
GET  /api/feedback/session/{session_id}
```

> Nếu specification gốc dùng `/api/compare`, **không tự động đổi** `/api/comparisons` thành `/api/compare` khi implementation hiện tại và tests đã dùng `/api/comparisons`.

### 5. Frontend routes hiện tại cần được bảo toàn

Các route hiện tại cần được coi là hợp lệ:

```text
/
/results/[sessionId]
/compare/[comparisonId]
/products/[productId]
```

Không xóa hoặc đổi các dynamic route này chỉ vì cấu trúc mẫu phía dưới khác.

### 6. Các chức năng phải được audit

Codex phải kiểm tra ít nhất:

- Requirement Analyzer
- Clarification
- Query Generator
- Gemini/LLM integration
- Search Provider abstraction
- Tavily/Live Search nếu có
- Demo Mode
- Live Mode
- Product extraction
- Price parser
- Rating parser
- Review count parser nếu có
- Text normalization
- Product normalization
- Deduplication
- Product / Product Offer separation
- Hard Filter
- Budget scoring
- Requirement scoring
- Purpose scoring
- Rating scoring
- Review scoring
- Source scoring
- Final scoring
- Ranking
- Data Confidence
- Evidence validation
- Recommendation
- AI explanation
- Product API
- Comparison
- Feedback
- History
- Cache
- Retry
- Timeout
- Fallback
- Logging
- Error handling
- Frontend integration
- Unit tests
- Integration tests
- End-to-end tests nếu có
- README
- Documentation
- Docker/deployment nếu có

### 7. Quy tắc sửa code

Khi được cho phép sửa:

- Chỉ sửa file cần thiết.
- Trước khi sửa phải liệt kê ngắn gọn file sẽ thay đổi và lý do.
- Không xóa chức năng đang hoạt động.
- Không làm lộ API key hoặc secret.
- Không chỉnh `.env` chứa secret của người dùng.
- Không hard-code secret vào source.
- Không bỏ validation, logging hoặc error handling hiện có.
- Không sửa business logic chỉ để “đẹp code” nếu không có lợi ích rõ ràng.
- Không làm giảm coverage hoặc bỏ test.
- Sau mỗi nhóm thay đổi phải chạy test phù hợp.
- Nếu sửa frontend phải chạy build lại.
- Nếu test/build fail phải sửa nguyên nhân, không che lỗi.

### 8. Thứ tự ưu tiên khi phát hiện vấn đề

Báo cáo và xử lý theo:

1. `CRITICAL` — không chạy, mất dữ liệu, security, API hỏng, pipeline hỏng.
2. `HIGH` — chức năng cốt lõi sai hoặc test/build fail.
3. `MEDIUM` — thiếu tính năng specification nhưng không phá luồng chính.
4. `LOW` — refactor, documentation, UX nhỏ, tối ưu không cấp thiết.

### 9. Definition of Done cho lần audit/sửa

Một đợt sửa chỉ được coi là hoàn thành khi:

- Backend tests liên quan pass.
- Toàn bộ test suite không có regression mới.
- Frontend build pass nếu frontend bị thay đổi.
- API contract hiện tại vẫn tương thích hoặc mọi breaking change đã được giải thích trước.
- Không mất chức năng đã có.
- Có báo cáo file đã sửa và kết quả kiểm tra.

---

# SPECIFICATION GỐC ĐÃ CHUYỂN TỪ FILE WORD

> Phần dưới giữ nguyên tinh thần và phần lớn câu chữ của tài liệu gốc.  
> Nếu có xung đột với **PROJECT OVERRIDES**, phải ưu tiên **PROJECT OVERRIDES**.

# MASTER PROMPT — XÂY DỰNG SOURCE CODE HOÀN CHỈNH
Bạn là Senior Software Architect + Senior Python Backend Engineer + Senior Next.js Engineer + AI Engineer + Recommendation Engineer.
Nhiệm vụ ban đầu của specification là xây dựng từ đầu đến cuối một hệ thống web hoàn chỉnh có tên:
SMART SHOPPING AI
Tên đề tài:
“XÂY DỰNG HỆ THỐNG TRỢ LÝ MUA HÀNG THÔNG MINH ỨNG DỤNG TRÍ TUỆ NHÂN TẠO”
Mục tiêu là tạo ra một project có thể chạy local thực tế, source code đầy đủ, có frontend, backend, database, AI/LLM, Web Search, product extraction, normalization, filtering, recommendation, ranking, explanation, comparison, history, cache, logging, error handling, testing và documentation.

## I. MỤC TIÊU CUỐI CÙNG
Hệ thống cho phép người dùng nhập nhu cầu mua hàng bằng ngôn ngữ tự nhiên.
Ví dụ:
“Tôi có 500 nghìn, cần mua tai nghe để học online, cần mic tốt, pin lâu.”
Hoặc:
“Tôi có 5 triệu, cần điện thoại để chụp ảnh và chơi game, ưu tiên camera tốt, pin lâu.”
Hoặc:
“Tôi cần laptop khoảng 15 triệu để học lập trình.”
Hệ thống phải:
Hiểu câu hỏi.
Xác định loại sản phẩm.
Xác định ngân sách.
Xác định mục đích.
Xác định thương hiệu.
Xác định yêu cầu.
Xác định yêu cầu loại trừ.
Xác định mức độ ưu tiên.
Xác định thông tin còn thiếu.
Hỏi lại người dùng nếu yêu cầu chưa đủ rõ.
Tạo search query.
Tìm sản phẩm thực tế trên Internet.
Thu thập dữ liệu từ nguồn được phép truy cập.
Chuẩn hóa dữ liệu.
Phát hiện sản phẩm trùng.
Tách Product và Product Offer.
Lọc sản phẩm.
Tính điểm phù hợp.
Xếp hạng.
Chọn Top 3–5.
Tính Data Confidence.
Tạo giải thích.
Hiển thị bằng chứng và nguồn.
Cho phép xem website gốc.
Cho phép chọn 2–3 sản phẩm để so sánh.
Cho phép xem lịch sử.
Có cache.
Có fallback.
Có logging.
Có test.
Có Demo Mode.
Có tài liệu để thuyết trình.

## II. NGUYÊN TẮC KIẾN TRÚC BẮT BUỘC
Không được xây hệ thống theo kiểu:
USER → LLM → LLM tự quyết định tất cả.
Phải xây:
USER ↓ LLM hiểu yêu cầu ↓ VALIDATION ↓ SEARCH ↓ EXTRACTION ↓ NORMALIZATION ↓ DEDUPLICATION ↓ HARD FILTER ↓ SCORING ENGINE ↓ RANKING ↓ EVIDENCE VALIDATION ↓ LLM EXPLANATION ↓ FRONTEND
LLM không được là nguồn sự thật duy nhất.

## III. PHÂN CHIA TRÁCH NHIỆM AI VÀ BACKEND
LLM được phép làm
Natural Language Understanding.
Requirement Analysis.
Requirement Extraction.
Clarification Question Generation.
Search Query Generation.
Product Information Extraction Support.
Explanation.
Product Comparison.
Natural Language Response.
LLM không được tự quyết định
Giá cuối cùng nếu không có dữ liệu nguồn.
Rating nếu không có dữ liệu nguồn.
Review count nếu không có dữ liệu nguồn.
URL.
Product ID.
Database ID.
Final score.
Budget filtering.
Hard filtering.
Product deduplication.
Source validation.
Python Backend chịu trách nhiệm
Input validation.
Schema validation.
Business validation.
Price parsing.
Rating parsing.
Product normalization.
Product deduplication.
Hard filtering.
Score calculation.
Ranking.
Confidence calculation.
Cache.
Error handling.
Retry.
Timeout.
Logging.
Database.

## IV. CÔNG NGHỆ BẮT BUỘC
Sử dụng stack sau.
Frontend
Next.js
TypeScript
Tailwind CSS
Backend
Python
FastAPI
Pydantic
SQLAlchemy
AI
Gemini API
Structured Output
Search
Dùng Search Provider abstraction.
Provider mặc định:
Tavily Search API.
Thiết kế để sau này có thể thay provider mà không sửa toàn bộ backend.
Database
MVP:
SQLite.
Production-ready:
PostgreSQL.
Cache
MVP:
Database cache.
Thiết kế abstraction để sau này thay bằng Redis.

## V. KIẾN TRÚC HỆ THỐNG
Phải triển khai theo kiến trúc:
USER
  ↓
NEXT.JS FRONTEND
  ↓
FASTAPI
  ↓
ORCHESTRATOR
  ↓
┌───────────────────────────────────────┐
│ AI REQUIREMENT ANALYZER               │
└───────────────────┬───────────────────┘
                    ↓
              VALIDATION
                    ↓
             CLARIFICATION?
             /          \
           YES           NO
            ↓             ↓
      ASK USER        QUERY GENERATOR
                          ↓
                    WEB SEARCH
                          ↓
                  SOURCE FILTERING
                          ↓
                 PRODUCT EXTRACTION
                          ↓
                 NORMALIZATION
                          ↓
                 DEDUPLICATION
                          ↓
                    HARD FILTER
                          ↓
                  SCORING ENGINE
                          ↓
                      RANKING
                          ↓
                   TOP 3–5
                          ↓
                 DATA CONFIDENCE
                          ↓
               EVIDENCE VALIDATION
                          ↓
                  AI EXPLANATION
                          ↓
                       RESULT
                          ↓
                    FRONTEND

## VI. PROJECT STRUCTURE BẮT BUỘC
Project phải có cấu trúc:
smart-shopping-ai/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── requirements.py
│   │   │       ├── search.py
│   │   │       ├── products.py
│   │   │       ├── compare.py
│   │   │       ├── history.py
│   │   │       └── health.py
│   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── constants.py
│   │
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── search_session.py
│   │   │   ├── requirement.py
│   │   │   ├── search_query.py
│   │   │   ├── source.py
│   │   │   ├── product.py
│   │   │   ├── product_offer.py
│   │   │   ├── recommendation.py
│   │   │   ├── comparison.py
│   │   │   └── feedback.py
│   │
│   │   ├── schemas/
│   │   │   ├── requirement.py
│   │   │   ├── search.py
│   │   │   ├── product.py
│   │   │   ├── recommendation.py
│   │   │   ├── comparison.py
│   │   │   ├── history.py
│   │   │   └── common.py
│   │
│   │   ├── services/
│   │   │   ├── llm/
│   │   │   │   ├── client.py
│   │   │   │   ├── prompts.py
│   │   │   │   ├── requirement_analyzer.py
│   │   │   │   ├── query_generator.py
│   │   │   │   ├── extractor.py
│   │   │   │   └── explanation.py
│   │   │
│   │   │   ├── search/
│   │   │   │   ├── base.py
│   │   │   │   └── tavily_provider.py
│   │   │
│   │   │   ├── extraction/
│   │   │   │   └── product_extraction_service.py
│   │   │
│   │   │   ├── normalization/
│   │   │   │   ├── price_parser.py
│   │   │   │   ├── rating_parser.py
│   │   │   │   └── product_normalizer.py
│   │   │
│   │   │   ├── deduplication/
│   │   │   │   └── product_deduplicator.py
│   │   │
│   │   │   ├── filtering/
│   │   │   │   └── product_filter.py
│   │   │
│   │   │   ├── scoring/
│   │   │   │   ├── budget_score.py
│   │   │   │   ├── requirement_score.py
│   │   │   │   ├── purpose_score.py
│   │   │   │   ├── rating_score.py
│   │   │   │   ├── source_score.py
│   │   │   │   └── scoring_engine.py
│   │   │
│   │   │   ├── recommendation/
│   │   │   │   └── recommendation_service.py
│   │   │
│   │   │   ├── comparison/
│   │   │   │   └── comparison_service.py
│   │   │
│   │   │   ├── cache/
│   │   │   │   └── cache_service.py
│   │   │
│   │   │   └── orchestration/
│   │   │       └── shopping_pipeline.py
│   │
│   │   ├── repositories/
│   │   │   ├── search_repository.py
│   │   │   ├── product_repository.py
│   │   │   ├── recommendation_repository.py
│   │   │   └── history_repository.py
│   │
│   │   └── utils/
│   │       ├── text.py
│   │       ├── url.py
│   │       ├── time.py
│   │       └── hashing.py
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── fixtures/
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   ├── results/
│   │   ├── compare/
│   │   └── history/
│   │
│   ├── components/
│   │   ├── SearchBox.tsx
│   │   ├── VoiceButton.tsx
│   │   ├── RequirementSummary.tsx
│   │   ├── SearchProgress.tsx
│   │   ├── ProductCard.tsx
│   │   ├── ProductGrid.tsx
│   │   ├── ScoreBreakdown.tsx
│   │   ├── ConfidenceBadge.tsx
│   │   ├── EvidenceList.tsx
│   │   ├── ComparisonTable.tsx
│   │   ├── AIExplanation.tsx
│   │   ├── EmptyState.tsx
│   │   └── ErrorState.tsx
│   │
│   ├── hooks/
│   ├── lib/
│   │   ├── api.ts
│   │   └── utils.ts
│   │
│   ├── types/
│   │   ├── requirement.ts
│   │   ├── product.ts
│   │   └── recommendation.ts
│   │
│   └── public/
│
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── api.md
│   ├── testing.md
│   ├── demo.md
│   └── presentation.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── LICENSE
Không được bỏ qua các thư mục quan trọng chỉ để làm code ngắn hơn.

## VII. REQUIREMENT ANALYSIS
AI phải chuyển input tự nhiên thành schema:
{
  "category": "tai nghe",
  "budget_min": null,
  "budget_max": 500000,
  "currency": "VND",
  "purpose": [
    "học online"
  ],
  "brands": [],
  "requirements": [
    {
      "name": "microphone",
      "value": "tốt",
      "priority": 5
    },
    {
      "name": "battery",
      "value": "pin lâu",
      "priority": 4
    }
  ],
  "excluded_requirements": [],
  "sort_preference": "best_match",
  "confidence": 0.95
}
Priority
1 = thấp
2 = khá thấp
3 = trung bình
4 = cao
5 = rất cao
Confidence
0.00–0.59:
Thiếu thông tin nghiêm trọng.

0.60–0.79:
Có thể tìm kiếm nhưng nên cân nhắc hỏi lại.

0.80–1.00:
Đủ thông tin.
Nếu requirement thiếu dữ liệu quan trọng thì chuyển sang Clarification.

## VIII. CLARIFICATION
Ví dụ:
Input:
“Tìm laptop tốt.”
AI hỏi:
“Bạn dự kiến ngân sách khoảng bao nhiêu?”
Sau khi nhận câu trả lời, tiếp tục hỏi nếu cần.
Mục tiêu:
Không tìm kiếm khi yêu cầu chưa đủ rõ.
Không hỏi quá nhiều câu cùng lúc.
Mỗi lượt chỉ hỏi những thông tin ảnh hưởng đáng kể đến recommendation.

## IX. QUERY GENERATOR
AI tạo tối đa 4 query.
Ví dụ:
tai nghe học online dưới 500000 microphone tốt
tai nghe bluetooth dưới 500k mic tốt pin lâu
tai nghe học online pin lâu dưới 500k
tai nghe microphone tốt giá dưới 500000
Không tạo vô hạn query.

## X. SEARCH PROVIDER
Tạo interface:
class SearchProvider:
    async def search(self, query: str) -> list:
        ...
Provider mặc định:
TavilyProvider
Thiết kế để sau này có thể thêm provider khác.
Không viết logic Tavily trực tiếp vào route.

## XI. NGUYÊN TẮC WEB ACCESS
Chỉ sử dụng dữ liệu có thể truy cập hợp pháp.
Không:
bypass CAPTCHA.
bypass login.
bypass robots.txt.
bypass anti-bot.
sử dụng dữ liệu trái phép.
Nếu source không truy cập được:
skip source
Không làm crash toàn bộ pipeline.

## XII. PRODUCT SCHEMA
Chuẩn product:
{
  "name": null,
  "brand": null,
  "model": null,
  "image_url": null,
  "rating": null,
  "review_count": null,
  "specifications": {},
  "pros": [],
  "cons": [],
  "normalized_name": null
}
Offer:
{
  "merchant": null,
  "price": null,
  "currency": "VND",
  "availability": null,
  "product_url": null,
  "source_domain": null,
  "retrieved_at": null
}
Source:
{
  "url": null,
  "domain": null,
  "title": null,
  "reliability_score": null,
  "retrieved_at": null
}
Không tự bịa field bị thiếu.

## XIII. EVIDENCE
Dữ liệu quan trọng nên có evidence:
price_evidence
rating_evidence
review_evidence
specification_evidence
Nếu không có evidence:
null
Explanation AI chỉ được phép sử dụng dữ liệu được cung cấp bởi backend.

## XIV. NORMALIZATION
Phải chuẩn hóa:
Price
399.000đ
399,000 VND
399K
0.399 triệu
→
399000
Rating
4.6
4,6/5
4.6/5
→
4.6
Brand/Model
Normalize để phục vụ deduplication.

## XV. DEDUPLICATION
Không lưu cùng một sản phẩm từ nhiều shop thành nhiều Product.
Ví dụ:
Sony WH-CH520
├── Shop A — 999000
├── Shop B — 949000
└── Shop C — 1029000
Database:
products
    ↓
product_offers
Ưu tiên match bằng:
Brand + Model.
Normalized name.
Similarity.
Evidence.
Không merge nếu chưa đủ chắc chắn.

## XVI. HARD FILTER
Lọc theo thứ tự:
Category.
Budget.
Required brand.
Excluded requirements.
Availability.
Ví dụ:
Budget max = 500000.
450000 → PASS
500000 → PASS
550000 → FAIL
Nếu budget là điều kiện bắt buộc, sản phẩm vượt ngân sách không được lọt vào Top Recommendation.

## XVII. MISSING DATA
Không được coi:
null
là:
false
Ví dụ:
Không có thông tin pin.
Hiển thị:
“Không có thông tin.”
Không được viết:
“Pin kém.”

## XVIII. RECOMMENDATION ENGINE
Final Score phải được tính bằng Python.
Công thức mặc định:
Final Score =
Budget × 25%
+ Requirement × 30%
+ Purpose × 20%
+ Rating × 10%
+ Reviews × 5%
+ Source × 10%
Tổng:
100%
Score nằm trong:
0–100
Không cho LLM tự đưa ra final score.

## XIX. SCORE BREAKDOWN
Mỗi recommendation phải có:
{
  "final_score": 94.2,
  "breakdown": {
    "budget": 25,
    "requirements": 28.5,
    "purpose": 18,
    "rating": 9.2,
    "reviews": 4.5,
    "source": 9
  }
}
Frontend phải hiển thị breakdown.

## XX. SOURCE SCORE
Mặc định cấu hình:
Official brand = 100
Trusted retailer = 90
Established marketplace = 80
Review website = 70
Unknown source = 50
Các giá trị phải tập trung trong config/constants.
Không hard-code rải rác.

## XXI. DATA CONFIDENCE
Tách:
AI MATCH
và:
DATA CONFIDENCE
Ví dụ:
AI MATCH: 94%
DATA CONFIDENCE: 91%
Confidence phụ thuộc:
Source quality.
Data completeness.
Freshness.
Cross-source agreement nếu có.

## XXII. TOP K
Mặc định:
TOP_K = 5
Nhưng nếu chỉ có 2 sản phẩm phù hợp thì trả 2.
Không bịa thêm sản phẩm để đủ Top 5.

## XXIII. AI EXPLANATION
Input cho AI:
User Requirement
+
Product
+
Score Breakdown
+
Evidence
Prompt phải yêu cầu:
Không bịa.
Không tự suy đoán.
Không thay đổi giá.
Không tạo rating.
Không tạo thông số.
Nếu thiếu thông tin phải nói rõ.
Output:
{
  "summary": "...",
  "pros": [],
  "cons": [],
  "matched_requirements": [],
  "unmet_requirements": [],
  "cautions": []
}

## XXIV. COMPARISON
User chọn tối đa 3 sản phẩm.
Endpoint:
POST /api/compare
Input:
{
  "session_id": "uuid",
  "product_ids": [1,2,3]
}
AI phải tạo:
Bảng so sánh.
Điểm mạnh.
Điểm yếu.
Mức độ phù hợp.
Kết luận.
Sản phẩm phù hợp nhất.
Không được tạo dữ liệu ngoài product payload.

## XXV. API CONTRACT
Phải xây các API:
POST /api/requirements/analyze
POST /api/requirements/clarify
POST /api/search
GET  /api/search/{session_id}
POST /api/compare
GET  /api/history
GET  /api/history/{session_id}
GET  /api/products/{product_id}
GET  /api/health
GET  /api/system/status

## XXVI. SEARCH API RESPONSE
{
  "session_id": "uuid",
  "requirement": {},
  "products": [],
  "recommendations": [],
  "total_found": 0,
  "total_filtered": 0,
  "warnings": [],
  "processing_time_ms": 0
}

## XXVII. DATABASE TABLES
Bắt buộc:
users
search_sessions
requirements
search_queries
sources
products
product_offers
recommendations
comparison_sessions
feedback

## XXVIII. SEARCH SESSION
id
user_id
raw_query
status
created_at
completed_at
processing_time_ms
Status:
PENDING
PROCESSING
COMPLETED
FAILED

## XXIX. REQUIREMENT
id
session_id
category
budget_min
budget_max
currency
purpose
brands
requirements
excluded_requirements
sort_preference
confidence
created_at

## XXX. PRODUCT
id
name
brand
model
normalized_name
image_url
rating
review_count
specifications
pros
cons
created_at
updated_at

## XXXI. PRODUCT OFFER
id
product_id
merchant
price
currency
availability
source_id
product_url
last_checked_at

## XXXII. RECOMMENDATION
id
session_id
product_id
final_score
budget_score
requirement_score
purpose_score
rating_score
review_score
source_score
confidence
rank
explanation
created_at

## XXXIII. CACHE
Search cache phải sử dụng normalized requirement.
Cache key gồm:
category
budget
purpose
brands
requirements
Hash thành key.
TTL mặc định:
15–60 phút
Giá có thể sử dụng TTL ngắn hơn.
Cache phải có abstraction.

## XXXIV. FALLBACK
Nếu Gemini lỗi:
Retry.
Nếu vẫn lỗi, fallback.
Không crash.
Nếu Search lỗi:
Retry.
Kiểm tra cache.
Nếu không có cache → thông báo lỗi.
Nếu một source lỗi:
skip source
continue

## XXXV. RETRY / TIMEOUT
Mặc định:
LLM timeout = 30 seconds
Search timeout = 15 seconds

LLM retry = 2
Search retry = 1
Không retry vô hạn.
Sử dụng exponential backoff nếu phù hợp.

## XXXVI. LOGGING
Mỗi request ghi:
request_id
session_id
timestamp
duration
LLM latency
search latency
number of queries
number of results
number of products
number of recommendations
error
Không bao giờ log API key.

## XXXVII. SECURITY
API key chỉ được lưu ở backend.
Không để:
GEMINI_API_KEY
TAVILY_API_KEY
trong frontend.
Dùng .env.
Phải có:
.env.example
Không commit:
.env
Input phải được giới hạn độ dài.
Không trả stack trace nội bộ cho frontend production.

## XXXVIII. FRONTEND
Trang chủ cần có:
Smart Shopping AI

Bạn đang muốn mua gì?

[ Textarea ]

[ 🎤 ]

[ Tìm sản phẩm bằng AI ]
Thêm preset:
Laptop
Điện thoại
Tai nghe
Chuột
Bàn phím
Màn hình

## XXXIX. FILTER UI
Có:
Category.
Budget.
Brand.
Sort by AI Match.
Sort by Price.
Sort by Rating.
Các filter bổ sung sau khi có kết quả không được phá pipeline backend.

## XL. LOADING UI
Không chỉ hiển thị “Loading…”.
Hiển thị:
✓ Phân tích nhu cầu
✓ Tạo truy vấn
✓ Tìm kiếm Internet
● Thu thập sản phẩm
○ Chuẩn hóa
○ Chấm điểm
○ Xếp hạng

## XLI. PRODUCT CARD
Mỗi card:
Image
Name
Brand
Price
Rating
Review count
AI Match
Data Confidence
Specifications
Pros
Cons
Source
Retrieved time
View product
Add to compare
Why AI recommends

## XLII. SCORE BREAKDOWN UI
Hiển thị:
AI MATCH 94%

Budget         25/25
Requirements   28.5/30
Purpose         18/20
Rating           9/10
Reviews          4.5/5
Source           9/10

## XLIII. EVIDENCE UI
Mỗi thông tin quan trọng nên có:
Nguồn
Thời điểm kiểm tra
URL
Ví dụ:
Pin: 30 giờ
Nguồn: Example Store
Kiểm tra: 24/08/2026

## XLIV. HISTORY UI
Hiển thị:
24/08/2026
Laptop 15 triệu học lập trình
5 sản phẩm

[ Xem lại ]

## XLV. COMPARISON UI
Bảng:
Product A   Product B   Product C

Price
Rating
Reviews
Battery
Microphone
Camera
AI Score
Confidence
Có:
[ So sánh bằng AI ]

## XLVI. FEEDBACK
Thêm:
👍 Hữu ích
👎 Không phù hợp
Lý do:
Giá cao
Không đúng nhu cầu
Sai sản phẩm
Muốn thương hiệu khác
Khác

## XLVII. VOICE
Voice chỉ là tính năng bổ sung.
Kiến trúc:
Browser microphone
↓
Speech-to-Text
↓
Text
↓
Requirement Analyzer
Không để voice làm dependency bắt buộc của MVP.

## XLVIII. DEMO MODE
Bắt buộc có:
DEMO_MODE=true
Demo Mode sử dụng dữ liệu mock để:
Chạy không cần API.
Demo ổn định.
Test recommendation.
Test frontend.
Live Mode:
DEMO_MODE=false
sẽ sử dụng Gemini + Search API thật.

## XLIX. TESTING
Phải có unit test cho:
Price parser.
Rating parser.
Normalization.
Filter.
Deduplication.
Scoring.
Ranking.
Phải có integration test cho:
Requirement pipeline.
Search pipeline.
Recommendation pipeline.
Compare pipeline.
Phải test:
Requirement đầy đủ.
Requirement thiếu budget.
Requirement thiếu category.
Brand.
Exclusion.
Nhiều criteria.
Không tìm thấy sản phẩm.
Gemini error.
Search error.
Product thiếu price.
Product thiếu rating.
Product duplicate.
Product vượt budget.
Input tiếng Việt không dấu.
Input dài.
Compare.
History.
Cache.
Fallback.

## L. TEST MODE
Không được phụ thuộc API thật cho toàn bộ unit test.
Sử dụng:
mock LLM
mock Search Provider
fixture products
Mục tiêu:
Test chạy ổn định ngay cả khi không có Internet.

## LI. DOCUMENTATION
Phải tạo:
README.md
docs/architecture.md
docs/database.md
docs/api.md
docs/testing.md
docs/demo.md
docs/presentation.md
README phải có:
Giới thiệu.
Kiến trúc.
Công nghệ.
Cài đặt.
Environment variables.
Cách chạy backend.
Cách chạy frontend.
Cách chạy test.
Cách bật demo mode.
Cách dùng live mode.
API.
Troubleshooting.

## LII. ENVIRONMENT VARIABLES
Tạo .env.example:
APP_ENV=development

DATABASE_URL=sqlite:///./smart_shopping.db

GEMINI_API_KEY=
GEMINI_MODEL=

TAVILY_API_KEY=

SECRET_KEY=

LLM_TIMEOUT_SECONDS=30
SEARCH_TIMEOUT_SECONDS=15

LLM_RETRY_COUNT=2
SEARCH_RETRY_COUNT=1

MAX_SEARCH_QUERIES=4
MAX_RESULTS_PER_QUERY=5

TOP_K=5

DEMO_MODE=true
CACHE_TTL_SECONDS=1800
Không được hard-code key.

## LIII. CÁCH IMPLEMENT
Không được xuất code giả.
Không được viết:
# TODO implement this
cho những phần quan trọng.
Mọi module quan trọng phải có code thực tế.
Nếu một API bên ngoài không thể sử dụng trong môi trường hiện tại:
Tạo interface thật.
Tạo implementation thật.
Tạo mock provider.
Cho hệ thống chạy ở DEMO_MODE.

## LIV. QUY TẮC VỀ CODE
Code phải:
Type hint.
Có docstring ở service quan trọng.
Có error handling.
Có logging.
Có validation.
Không duplicate logic.
Không hard-code business rule ở nhiều nơi.
Có config tập trung.
Có service abstraction.

## LV. QUY TẮC OUTPUT KHI XÂY SOURCE
Không được trả lời chung chung.
Mỗi giai đoạn phải ghi:
1. Mục tiêu
2. Files sẽ tạo
3. Cấu trúc thư mục sau bước
4. Code đầy đủ từng file
Dùng:
FILE: backend/app/main.py
sau đó mới đưa code.
Không được bỏ những file quan trọng.
5. Dependency
Ví dụ:
pip install ...
npm install ...
6. Cách chạy
7. Cách kiểm tra
8. Kết quả mong đợi
9. Những lỗi thường gặp

## LVI. QUY TRÌNH BUILD BẮT BUỘC
Phải triển khai theo thứ tự:

### PHASE 1 — FOUNDATION
Phân tích project.
Tạo cấu trúc thư mục.
Tạo backend.
Tạo frontend.
Environment.
Database.
Health check.
Test framework.

### PHASE 2 — AI
Gemini client.
Structured output.
Requirement schema.
Requirement Analyzer.
Validation.
Clarification.
Query Generator.

### PHASE 3 — SEARCH
SearchProvider interface.
TavilyProvider.
Search service.
Source filtering.
Search cache.

### PHASE 4 — PRODUCT
Product schema.
Extraction.
Normalization.
Deduplication.
Product / Offer separation.

### PHASE 5 — RECOMMENDATION
Hard Filter.
Budget scoring.
Requirement scoring.
Purpose scoring.
Rating scoring.
Review scoring.
Source scoring.
Final scoring.
Ranking.
Confidence.

### PHASE 6 — AI RESPONSE
Evidence validation.
Explanation.
Comparison.

### PHASE 7 — FRONTEND
Home.
Search.
Loading.
Requirement Summary.
Product cards.
Score breakdown.
Compare.
History.
Error states.

### PHASE 8 — RELIABILITY
Retry.
Timeout.
Fallback.
Logging.
Health check.
Demo Mode.

### PHASE 9 — TEST
Unit test.
Integration test.
End-to-end test.

### PHASE 10 — DOCUMENTATION
README.
Architecture.
Database.
API.
Testing.
Demo.
Presentation.

## LVII. BUILD STRATEGY
Không cố viết toàn bộ project trong một file.
Không tạo code “monolithic”.
Không tạo:
main.py
chứa toàn bộ logic.
Mỗi trách nhiệm phải có module riêng.

## LVIII. CHECKPOINT
Sau mỗi phase:
Compile backend.
Run tests.
Start backend.
Start frontend.
Verify endpoint.
Verify UI nếu phase liên quan frontend.
Không chuyển phase nếu phase trước đang lỗi nghiêm trọng.

## LIX. DEFINITION OF DONE
Project được xem là hoàn thành khi:
[ ] Backend chạy
[ ] Frontend chạy
[ ] Database chạy
[ ] Requirement Analyzer chạy
[ ] Clarification chạy
[ ] Query Generator chạy
[ ] Search chạy
[ ] Product Extraction chạy
[ ] Normalization chạy
[ ] Deduplication chạy
[ ] Filtering chạy
[ ] Scoring chạy
[ ] Ranking chạy
[ ] Confidence chạy
[ ] Explanation chạy
[ ] Compare chạy
[ ] History chạy
[ ] Cache chạy
[ ] Error handling chạy
[ ] Demo mode chạy
[ ] Unit tests pass
[ ] Integration tests pass
[ ] README hoàn chỉnh
[ ] API documentation hoàn chỉnh
[ ] Presentation documentation hoàn chỉnh

## LX. DEMO SCENARIO
Demo chính:
“Tôi có 5 triệu, cần điện thoại để chụp ảnh và chơi game,
ưu tiên camera tốt, pin lâu và không muốn máy quá nặng.”
Phải hiển thị:
Requirement.
Category.
Budget.
Purpose.
Requirements.
Priority.
Search queries.
Number of results.
Number after filter.
Top 5.
AI Score.
Data Confidence.
Score Breakdown.
Explanation.
Pros.
Cons.
Unmet requirements.
Source.
Compare 3 products.
AI conclusion.

## LXI. DEMO FALLBACK
Nếu Live API lỗi:
Enable DEMO_MODE=true
và demo phải vẫn chạy.

## LXII. CÂU HỎI BẢO VỆ
Phải có tài liệu trả lời:
AI được sử dụng ở đâu?
Requirement Analysis, Query Generation, Extraction Support, Explanation, Comparison, Clarification.
AI nhận gì?
Natural language + product evidence.
AI tạo gì?
Structured Requirement, Queries, Extraction, Explanation.
Sản phẩm lấy ở đâu?
Web Search / Publicly accessible sources / Official APIs.
Vì sao cần Web Search?
Dữ liệu sản phẩm và giá thay đổi liên tục.
Recommendation hoạt động thế nào?
Hard Filter + Weighted Scoring + Ranking.
Vì sao không để LLM quyết định score?
Để score deterministic, reproducible và explainable.
Database làm gì?
History, cache, sessions, products, offers, recommendations.
Backend làm gì?
API, orchestration, validation, scoring, data processing.
Frontend làm gì?
Input, loading, results, comparison, history.
Hạn chế?
Search provider dependency.
Website format thay đổi.
Giá thay đổi.
Dữ liệu thiếu.
AI có thể hiểu sai input.
Không đảm bảo mọi nguồn chính xác tuyệt đối.
Hướng phát triển?
Voice.
Personalized recommendation.
Price tracking.
Notifications.
Vector search.
Hybrid search.
Feedback learning.
Multi-agent.

## LXIII. KIẾN TRÚC TƯ DUY CUỐI CÙNG
Toàn bộ hệ thống phải tuân theo:
UNDERSTAND
↓
VALIDATE
↓
SEARCH
↓
EXTRACT
↓
NORMALIZE
↓
DEDUPLICATE
↓
FILTER
↓
SCORE
↓
RANK
↓
EXPLAIN
↓
SHOW EVIDENCE
Không được biến thành:
USER
↓
LLM
↓
LLM tự chọn sản phẩm
↓
LLM tự bịa thông tin

## LXIV. YÊU CẦU ĐẶC BIỆT KHI THỰC HIỆN
Đối với project hiện tại, hãy audit và hoàn thiện project theo specification này; không xây lại từ đầu.
Không tự ý thay đổi stack công nghệ nếu không có lý do kỹ thuật mạnh.
Nếu cần thay đổi, phải giải thích trước thay đổi đó.
Không bỏ qua code quan trọng.
Không dùng pseudo-code cho module cốt lõi.
Không hard-code API key.
Không tự bịa dữ liệu sản phẩm.
Không bypass website security.
Không để LLM quyết định final recommendation score.
Phải có mock/demo provider để hệ thống chạy được ngay cả khi API chưa được cấu hình.
Phải ưu tiên độ ổn định hơn việc thêm quá nhiều tính năng.
Phải ưu tiên MVP hoàn chỉnh trước.
Sau khi MVP chạy ổn định mới thêm tính năng nâng cao.
Sau mỗi phase phải test.
Mọi API phải có schema request/response rõ ràng.
Mọi external API phải có timeout và retry.
Mỗi error phải có thông báo dễ hiểu.
Source code phải có cấu trúc chuyên nghiệp.
README phải đủ để một sinh viên mới clone project và chạy từ đầu.
Project cuối cùng phải có thể dùng làm nền cho đồ án tốt nghiệp.

## LXV. THỨ TỰ TRẢ KẾT QUẢ CHO TÔI
Không được cố đưa toàn bộ hàng chục nghìn dòng code trong một câu trả lời duy nhất nếu điều đó làm code bị cắt hoặc thiếu.
Hãy chia thành các PART có thứ tự.
Mỗi PART phải hoàn chỉnh và liên kết với PART trước.
- **PART 01: Architecture + foundation.**
- **PART 02: Backend + database.**
- **PART 03: LLM + Requirement Analyzer.**
- **PART 04: Search + extraction.**
- **PART 05: Normalization + deduplication.**
- **PART 06: Filtering + scoring + recommendation.**
- **PART 07: Explanation + comparison.**
- **PART 08: Frontend.**
- **PART 09: History + cache + fallback.**
- **PART 10: Testing.**
- **PART 11: Docker + deployment.**
- **PART 12: README + demo + presentation.**
Ở mỗi PART:
Nêu file mới.
Nêu file thay đổi.
Cung cấp full code.
Không được cung cấp đoạn code thiếu context.
Không phá vỡ code của PART trước.

## LXVI. BƯỚC KHỞI ĐỘNG
Trong tài liệu gốc, quy trình khởi động được mô tả là:

### PHASE 1 — FOUNDATION
Phải thực hiện:
Phân tích kiến trúc.
Xác định folder structure.
Tạo backend FastAPI.
Tạo frontend Next.js.
Tạo .env.example.
Tạo config.
Tạo database setup.
Tạo SQLAlchemy base.
Tạo health endpoint.
Tạo test framework.
Tạo README nền.
Kiểm tra compile.
Chạy test.
Hướng dẫn cách chạy.
Khi xây mới, sau Phase 1 sẽ tiếp tục Phase 2; với project hiện tại, chỉ dùng thứ tự này để audit mức độ hoàn thiện.
Không bỏ qua các bước kiểm tra.
Mục tiêu cuối cùng là:
Một project Smart Shopping AI hoàn chỉnh, chạy được local, có Live Mode + Demo Mode, có AI + Web Search + Recommendation + Explanation + Comparison + History + Cache + Testing + Documentation, đủ chất lượng để phát triển thành đồ án tốt nghiệp.