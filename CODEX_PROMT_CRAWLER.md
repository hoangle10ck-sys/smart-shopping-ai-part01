Prompt cho Codex — triển khai Real Product Collector theo TASKS.md
Bạn là Senior Python Backend Engineer, Data Engineer và Web Extraction Engineer. Hãy thực thi code thật, không chỉ đề xuất hướng đi, trên repository ThinhLoLem/smart-shopping-ai-part01 đang mở trong workspace.
Mục tiêu duy nhất trong đợt này: hoàn thiện công đoạn thu thập dữ liệu sản phẩm thật từ nguồn công khai được phép truy cập → xác minh tên/giá/biến thể → chuẩn hóa → upsert SQLite → chuyển dữ liệu đã lưu cho recommendation đang có. Sau khi hoàn tất, một người dùng nhập nhu cầu sẽ có thể tìm và nhận đề xuất dựa trên dữ liệu thật, khi tồn tại nguồn có quyền truy cập phù hợp. Không sửa lại Scoring Engine một cách không cần thiết và không tạo một recommendation system thứ hai.
Hướng dẫn điều hành
1. Mở TASKS.md ở root, đọc toàn bộ và coi đây là nguồn sự thật về checklist, thứ tự phụ thuộc, DoD, chính sách truy cập, báo cáo/checkpoint. Nếu project đã có TASKS.md/tiến độ khác, hãy merge thay vì xóa bỏ.
2. Kiểm tra git status, README, docs, configs, actual ORM/Pydantic/API, tests. Đọc các file thực tế trước khi tạo bất cứ module mới nào. Bảo vệ worktree; không xóa code user. Ưu tiên một nhánh làm việc riêng; không push/force-push.
3. Bắt đầu T00 và lần lượt T01–T10 theo thứ tự, làm từng phase thành các thay đổi nhỏ, chạy test sau mỗi phase, cập nhật checkbox và docs/CRAWLER_PROGRESS.md (lưu lệnh test + kết quả thật). Nếu task bị chặn thì ghi BLOCKED và làm phần độc lập tiếp theo, không hỏi xác nhận cho quyết định kỹ thuật thường lệ.
4. Nguồn thực ưu tiên: cấu hình allowlist các cửa hàng thật có WooCommerce Store API công khai hoặc HTML/JSON-LD trang sản phẩm công khai và có điều kiện sử dụng phù hợp; nếu có URL trực tiếp được phép thì hỗ trợ luôn. Tavily hiện có chỉ để discover URL. Không sử dụng DummyJSON để chứng minh giá/sản phẩm bán thực tế.
5. Thứ tự công nghệ bắt buộc: Public API JSON → HTTPX + JSON-LD/HTML deterministic extraction → Crawl4AI self-hosted browser fallback cho website JavaScript hợp lệ → LLM structured extraction (OpenAI/Gemini/Ollama tùy config) chỉ khi rule parser không đủ. Không dùng LLM để bịa giá/stock/SKU/đánh giá/bảo hành. Không ép cài Crawl4AI cho mọi môi trường hoặc bắt buộc cần AI key.
6. Phần Shopee/Lazada không được cam kết truy cập thành công. Làm site feasibility/preflight đúng robots/điều khoản; dừng khi CAPTCHA, 403/429 hoặc login. Không bypass bảo vệ website hoặc gọi API nội bộ không được cho phép. Khi sàn bị chặn, chọn nguồn công khai khác và trả trạng thái minh bạch.
7. Reuse thực sự SearchService, ProductPageValidator, ProductExtractionService, NormalizationService, ProductDeduplicator, Product, ProductOffer, Source, RawProductCandidate, CandidateBuilder, RecommendationService, RecommendationSnapshot. Tránh thay đổi contract/DB hiện hữu trừ khi có migration và regression tests. Phải có unique keys, idempotent import, price evidence + observed_at + currency + variant identity; không ghi đè snapshot lịch sử.
8. Trình bày Demo/Mock, Fixture-tested, Live Verified, Live Restricted và Live Not Verified rõ ràng. Khi chưa có nguồn thật hoặc không thể truy cập internet, hoàn thiện adapter + fixtures + offline tests, không tuyên bố dữ liệu thật đã lấy thành công.
9. Viết tests: data contracts, public API, JSON-LD, validation, SSRF, robots/policy, rate limit, 403/429/CAPTCHA, SKU/price, dedup, persistence, repeated ingest, stale, end-to-end query→DB→ranking; không gọi internet trong unit/integration tests. Tạo opt-in Live smoke test quy mô nhỏ và benchmark metrics có mẫu số, không giả số liệu.
10. Chạy toàn bộ backend tests, frontend tests/lint/build và E2E khi môi trường hỗ trợ. Cập nhật README/docs/runbook cùng câu lệnh chạy thật. Nếu thiếu browser/dependencies/keys, ghi hạn chế chính xác và tiếp tục.
Ưu tiên kỹ thuật để quyết định khi có xung đột
- Đúng nguồn + đúng sản phẩm + đúng giá + đúng SKU > số lượng URL lấy được.
- API công khai có điều khoản rõ ràng > HTML có cấu trúc > browser render > LLM extraction.
- Dữ liệu verified có nguồn > dữ liệu partial có nhãn > dữ liệu từ snippet không kiểm chứng.
- Tận dụng class và route có sẵn > kiến trúc mới phức tạp.
- Tái lập được bằng tests và source logs > những tuyên bố "crawl thành công" không có chứng cứ.
- Không sử dụng giá USD làm ngân sách VND; không đoán phí vận chuyển/voucher.
- Không thay đổi hành vi Demo Mode/Tavily cũ nếu không có lý do và tests.
Tiêu chí hoàn thành bắt buộc
- Có Source Registry/URL permission preflight.
- Có collector public storefront JSON và collector HTML/JSON-LD.
- Có Crawl4AI tùy chọn, không bypass chặn.
- Có valid ProductObservation/OfferEvidence, error statuses và timestamp.
- Có safe database migration nếu sửa schema; price history/idempotency.
- Có connection từ dữ liệu mới vào recommendation hiện tại.
- Có offline unit/integration/E2E khi khả thi và hướng dẫn chạy.
- Có report nguồn thực Live; chỉ ghi LIVE_VERIFIED nếu đã thực sự đọc một trang/API được phép, xác minh và lưu ít nhất một offer giá thật, nếu không báo BLOCKED/NOT_VERIFIED với nguyên nhân.
Bắt đầu triển khai từ T00 ngay bây giờ. Không dừng ở plan. Sau mỗi checkpoint, cập nhật TASKS.md và docs/CRAWLER_PROGRESS.md. Đầu ra báo cáo tiếng Việt gồm: file đã sửa, task DONE/BLOCKED, lệnh & kết quả test, số record thật và nguồn có timestamp, các hạn chế còn lại và bước tiếp theo. Không tự push code.