# MISS.md — Bảng điều khiển trạng thái dự án Smart Shopping AI

> **MISS** = Mission Status Dashboard (Mục tiêu & Trạng thái)
> Tạo: 2026-10-17 — từ phiên phân tích toàn diện repo + lập kế hoạch Unified Multi-Source Search
> File này **chỉ theo dõi trạng thái**, BỔ SUNG cho TASKS.md (crawler), TASKS_RESEARCH_DATA.md (research), docs/PROGRESS — không thay thế, không xóa lịch sử.

---

## 1. Tổng quan nhanh

| Thông số | Giá trị |
|---|---|
| Dự án | Smart Shopping AI — Trợ lý mua hàng thông minh |
| Trạng thái tổng | MVP hoàn chỉnh (Phase 1–7) + Research Catalog (R00–R09) + UI Redesign (A–H) |
| Nhánh Git | main @ f28a11a |
| Working tree | ⚠️ ~70 file sửa + ~100 file mới CHƯA COMMIT (rủi ro mất tiến độ) |
| Runtime | FastAPI :8000 + Next.js :3000 (local Windows) |
| Database | SQLite backend/smart_shopping.db — 2.18 MB, 20 bảng, WAL |
| API keys | ✅ TAVILY (verified) + ✅ GEMINI (verified) trong backend/.env — cả 2 KHÔNG commit git |
| AI hiện dùng | Demo: MockLLMClient (parser Python) · Live: OpenAI gpt-4o-mini (key rỗng) → **Gemini 3.6 Flash (key đã cấp + verified 2026-10-17)** → fallback local |

---

## 2. ✅ ĐÃ HOÀN THIỆN (đã xác minh bằng test/bằng chứng)

### 2.1 MVP Core — Phase 1–7 (FINAL_AUDIT: CRITICAL=0, HIGH=0)
- [x] Pipeline đầy đủ: analyze → clarify → query gen → search → extract → normalize → dedup → hard filter → score → rank → evidence → explain → snapshot
- [x] 16 API endpoints (health, requirements/analyze+clarify, search, recommendations, products, comparisons, feedback, history, research)
- [x] 20 bảng SQLAlchemy (WAL, FK on, busy_timeout 30s); create_all additive-only
- [x] LLM 3 tầng fallback: MockLLMClient (demo) → OpenAI → Gemini; LLM KHÔNG quyết định điểm số
- [x] Scoring 6 thành phần Python thuần + Top-K; không bịa dữ liệu để đủ K
- [x] RecommendationSnapshot bất biến + SearchCache SQLite TTL 1800s (Live-only)
- [x] Comparison 2–3 SP, winner deterministic (score→rating→reviews), cờ NOT_COMPARABLE
- [x] Feedback + History dùng chung DB local (đúng yêu cầu không đăng nhập)
- [x] ~972 backend pytest pass; conftest DB tạm isolation

### 2.2 Research Catalog — R00–R09
- [x] 191 SP Amazon Reviews 2023 (historical), 88 giá USD, 0 offer giả — RESEARCH_DATASET_VERIFIED
- [x] Adapter độc lập /api/research/*, immutable snapshot, USD/VND tách bạch, parser grammar local
- [x] Idempotent import (re-run: 0 mới / 46 duplicate); verification 191/191 raw records
- [x] Parser regressions 24 passed; research suite 40 passed
- ⏸ R08 PARTIAL: thiếu human labels → Precision@K/NDCG = N/A (xem Blocked)

### 2.3 Crawler Track — T00–T10 (phần offline)
- [x] Collector framework: HTTP collector, WooCommerce Store API, JSON-LD parser, Crawl4AI browser fallback
- [x] DNS rebinding guard, robots/policy preflight, fail-closed source registry
- [x] 64 collector tests offline (httpx.MockTransport); benchmark FIXTURE_TESTED_ONLY
- ⛔ Live ingestion 0 SP — xem mục Blocked

### 2.4 UI Redesign — Phase A–H
- [x] 5 routes responsive (375/768/1366/1920px, 0 horizontal overflow)
- [x] Design system Premium Minimalist (CSS tokens, tabular-nums, WCAG focus rings, skip link)
- [x] 48 FE unit tests + 18 Playwright E2E pass
- [x] UI_AUDIT.md + UI_QA_REPORT.md + UI_TASKS.md hoàn tất

### 2.5 Tư vấn đã chốt trong phiên phân tích (2026-10-17)
- [x] Xác định AI phân tích nhu cầu: MockLLMClient (demo, rule-based Python) / OpenAI GPT-4o-mini + Gemini 3.6 Flash (live, qua get_llm_client factory trong llm/client.py)
- [x] Đề xuất model Live: DeepSeek V4 (rẻ nhất ~$0.0004/request, OpenAI-compatible drop-in) hoặc Gemini Flash (free tier, SDK google-genai đã sẵn); GPT-5 mini nếu có thẻ quốc tế
- [x] Tư vấn local LLM: ỔN có điều kiện — Ollama CHƯA cài (verified OLLAMA_NOT_INSTALLED); khuyến nghị qwen3:8b nếu GPU ≥8GB VRAM; adapter ~50 dòng qua OpenAI-compatible endpoint localhost:11434/v1
- [x] Xác nhận lưu trữ: MỘT file SQLite cục bộ 2.18 MB — không cloud, không app mobile, web app full-stack
- [x] Tavily API key do user cấp (2026-10-17), verify live STATUS=OK (1 credit test) — lưu trong backend/.env (gitignored), KHÔNG commit
- [x] Gemini API key do user cấp (2026-10-17), verify generateContent OK — model gemini-3.6-flash (config mặc định) ĐÃ XÁC MINH tồn tại và hoạt động (đập tan nghi vấn chưa xác minh trong README); 50 models trong tài khoản; lưu trong backend/.env, KHÔNG commit

---

## 3. 🔄 ĐANG LÀM / CHỜ PHÊ DUYỆT

### Unified Multi-Source Search (kế hoạch đã nộp 2026-10-17)
Mục tiêu: bỏ dropdown chế độ dữ liệu, user nhập 1 câu → hệ thống tự tìm DB + Research + Demo + nguồn live khả dụng song song, hiển thị sớm + tăng cường, Top 10.

| Phase | Nội dung | Trạng thái |
|---|---|---|
| U1 — Backend | Orchestrator, adapters, route `search_scope=auto`, snapshot và response unified | ⏳ ĐANG LÀM — chưa có pytest xác nhận |
| U2 — Frontend | Bỏ lựa chọn mode/sàn, URL nâng cao, unified labels | ⏳ CHỜ U1 |
| U3 — E2E & Docs | Playwright theo UI mới, regression, docs | ⏳ CHỜ U2 |

**Lưu ý xác minh 2026-10-20:** working tree có nhiều thay đổi tracked và untracked không thuộc riêng Unified Search; không reset/commit/ghi đè. Frontend unit test có output `48 pass, 0 fail` cho thay đổi tạm thời, sau đó phần UI đã được trả lại tương thích; chưa rerun lần cuối. Pytest từng phát hiện lỗi compile; backend thay đổi trong lượt tiếp tục đã được hoàn nguyên, giữ nguyên trạng thái từ trước lượt này. SearchRequest mặc định backend vẫn `platforms`.

---

## 4. 📌 CẦN LÀM (backlog, ưu tiên giảm dần)

### 🔴 P0 — Vệ sinh & an toàn dữ liệu (1–2 ngày)
- [ ] Commit tiến độ hiện tại theo từng phần logic (research/crawler/UI) — RỦI RO LỚN NHẤT lúc này
- [ ] Xóa 8 dòng console.log/error trong frontend/app/page.tsx (dòng 92, 95, 119, 147, 153, 185, 196, 204) — debug residue, rò query người dùng ra console
- [ ] Quyết định số phận app/services/normalization_service.py TRÙNG LẶP với app/services/normalization/normalization_service.py (1 trong 2 là dead code)
- [ ] Sửa README: Next.js 16.3.3 → 16.4.1 (lệch package.json)

### 🔴 P0.5 — Unified Multi-Source Search
- [ ] Hoàn thiện/cập nhật thay đổi Unified sau khi xác nhận kế hoạch với working tree hiện tại.
- [ ] Test API auto, catalog đủ/thin, external success/failure, persistence/dedup, thiếu dữ liệu và giá/URL.
- [ ] Chạy focused pytest, frontend lint/build, regression và E2E.

### 🟠 P1 — Chất lượng & vận hành (3–7 ngày)
- [ ] Điền memory-bank/ (6 file đều rỗng template, CLAUDE.md yêu cầu bắt buộc đọc/cập nhật)
- [ ] Python lockfile (requirements.txt chỉ có ranges, không pin patch)
- [ ] Verify Docker trên máy có Docker (README có lệnh sẵn; hiện NOT RUNTIME VERIFIED)
- [ ] Cleanup job cho search_cache_entries hết TTL (hiện row cũ chỉ bị bỏ qua)
- [ ] Request_id correlation + structured logging (một số stage chưa có latency/trace)

### 🟡 P2 — Nâng cấp theo tư vấn đã chốt (cần user cho phép từng mục)
- [ ] (Tùy chọn) Thêm Ollama adapter cho local LLM — CHỜ cho phép cài dependency (Ollama chưa cài)
- [ ] (Tùy chọn) Đổi provider Live: DeepSeek V4 hoặc cấu hình Gemini/Tavily key — CHỜ user cấp key, KHÔNG tự sửa .env
- [ ] (Tùy chọn) Dark mode, History pagination, refactor 2 god file (product_extraction_service.py ≥1.695 dòng, llm/client.py ≥1.491 dòng)

### 🟢 P3 — Nghiên cứu (không gấp cho MVP)
- [ ] R08 human labels (2–3 người đánh giá độc lập điền relevance-labels.csv) → tính Precision@5/NDCG thật
- [ ] Time-decay cho freshness trong Data Confidence (cần regression trước khi đổi công thức)

---

## 5. ⛔ BLOCKED (không tự xử lý được)

| Blocker | Lý do | Cần gì để mở |
|---|---|---|
| Shopee/Lazada collector | ACCESS_RESTRICTED (anti-bot, điều khoản) — 2 cờ policy tắt, registry rỗng | Merchant được duyệt trong COLLECTOR_SOURCE_REGISTRY_JSON + bật 2 cờ policy (user/operator quyết định) |
| Live ingestion (0 SP thật) | Phụ thuộc mục trên | Cùng mục trên |
| Tavily Live search ✅ | ✅ ĐÃ MỞ KHÓA 2026-10-17 — key do user cấp, verify STATUS=OK bằng 1 request test live (tốn 1 credit free tier) | Key đã lưu trong backend/.env (file gitignored, KHÔNG commit vào git) — chờ bật Live (đổi DEMO_MODE=false + restart backend) hoặc Unified Search sẽ tự phát hiện |
| Docker runtime | Máy dev không có Docker CLI | Machine có Docker Desktop + chạy lệnh trong README |
| Ollama local LLM | Chưa cài + chưa có adapter | User cho phép cài + GPU đủ (8GB+ VRAM khuyến nghị cho qwen3:8b) |
| Precision@K / NDCG | Thiếu human labels (R08) | Người đánh giá độc lập điền 3.600 ô trống

---

## 6. 📊 Thống kê nhanh (2026-10-17)

| Hạng mục | Số liệu |
|---|---|
| Backend tests | ~972 pass (pytest, DB tạm isolation) |
| Frontend unit tests | 48 pass (node test runner) |
| E2E Playwright | 18 pass (4 viewport: 375/768/1366/1920) |
| API endpoints | 16 application + FastAPI /docs |
| Bảng DB | 20 (14 MVP + research/crawler additive) |
| Routes FE | 5 (/, results/[sessionId], products/[productId], compare/[comparisonId], history) |
| God files cần refactor | product_extraction_service.py ≥1.695 dòng; llm/client.py ≥1.491 dòng |

---

## 7. 📏 Quy tắc cập nhật file này

1. Đánh dấu [x] khi có BẰNG CHỨNG test/kiểm tra chạy thật — không ghi PASS khi chưa chạy.
2. Blocker ghi rõ lý do + điều kiện mở; không tự ý vượt chính sách (policy, key, chi phí API).
3. Unified Search: chỉ chuyển phase sang DONE khi regression full pass (pytest + npm test + lint + build + e2e).
4. File này BỔ SUNG cho TASKS.md (crawler) + TASKS_RESEARCH_DATA.md (research) + docs/PROGRESS — không thay thế, không xóa lịch sử.
5. Không commit/push tự ý; không sửa .env; không reset/migrate DB; không cài dependency khi chưa được cho phép.

---

*Phiên tạo: 2026-10-17 · Nguồn: phân tích toàn diện repo (read-only) + các phiên tư vấn (AI model, local LLM, cấu trúc repo, lưu trữ, kế hoạch Unified Search)*




