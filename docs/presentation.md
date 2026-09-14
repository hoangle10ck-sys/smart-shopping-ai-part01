# Kịch bản bảo vệ Smart Shopping AI

Thông điệp chính: nhu cầu tự nhiên được chuyển thành quy trình có kiểm tra, nguồn
dữ liệu và điểm số tái lập được. LLM hỗ trợ ngôn ngữ; Python quyết định lọc và điểm.

## Đề cương 12–15 phút

| Thời lượng | Nội dung | Bằng chứng |
|---|---|---|
| 0–2 phút | Bài toán, ngân sách, thông tin thiếu, mục tiêu MVP local | Home, câu tai nghe 500 nghìn |
| 2–4 phút | Kiến trúc, LLM/Python, Product/Offer | architecture.md, database.md |
| 4–8 phút | Analysis, search, recommendation, breakdown, matching và evidence | demo.md; điện thoại cho ví dụ camera unknown |
| 8–10 phút | Detail, comparison, feedback, History và snapshot | UI cùng regression comparison |
| 10–12 phút | Database test sạch, mock providers, E2E, lỗi và cache | testing.md, FINAL_AUDIT.md |
| 12–15 phút | Hạn chế, Docker chưa kiểm chứng runtime, hỏi đáp | Các câu dưới đây |

Chuẩn bị hai terminal theo README; xác nhận Demo trước buổi bảo vệ. Chạy trước
scenario tests và E2E. Dùng score từ demo.md, không dùng số minh họa của MASTER_SPEC
như kết quả thực. Demo nguồn giả lập không chứng minh chất lượng giá Live.

## 15 câu hỏi bảo vệ

1. **AI dùng ở đâu?** Live Analyzer gọi OpenAI/Gemini để trả structured requirement,
   qua Pydantic validation; explanation tạo narrative từ dữ liệu đã chấm.
   Clarification dựa dữ liệu thiếu. Query generator, extraction hiện tại và comparison
   là Python deterministic, không tuyên bố chúng đang gọi LLM.

2. **Backend deterministic làm gì?** Validation, parsing, normalization, dedup,
   category/budget/brand/exclusion filter, scoring/ranking, matching, confidence,
   evidence, snapshot/cache và xử lý lỗi. Cùng dữ liệu/config cho cùng điểm.

3. **Vì sao không để LLM quyết định final score?** Để kiểm thử, tái lập và giải thích.
   Trọng số cố định budget 25%, requirement 30%, purpose 20%, rating 10%, reviews 5%,
   source 10%. LLM không ghi đè dữ liệu số. AI Match không phải xác suất; Data
   Confidence là chất lượng dữ liệu riêng.

4. **Vì sao cần hard filter?** Rating cao không thể cứu sản phẩm sai category hoặc
   vượt ngân sách bắt buộc. Lọc trước, chấm sau. Category thiếu không được copy từ
   requirement để cho sản phẩm qua lọc.

5. **Vì sao Product / Product Offer?** Một model có nhiều merchant, giá, URL và thời
   điểm. Product giữ thông tin chung; Offer giữ thông tin bán theo nguồn. Không
   nhân bản recommendation chỉ vì cùng sản phẩm có nhiều link bán hàng.

6. **Deduplication hoạt động thế nào?** Match chính xác brand + model đã chuẩn hóa;
   nếu không đủ cặp này thì dùng normalized name, đồng thời tránh category xung đột.
   Điền dữ liệu còn thiếu, giữ offers riêng. Chưa có fuzzy similarity hoặc giải quyết
   mọi biến thể cấu hình/tên mơ hồ. Có unit tests riêng.

7. **Evidence để làm gì?** Cho biết giá trị từ nguồn/URL nào, lúc nào, reliability
   nếu có. Attribution đòi hỏi liên kết product/offer và cùng field value trong
   observation của session. Thiếu nguồn thì để trống, không gán merchant rẻ nhất
   làm nguồn của mọi specification.

8. **matched/unmet/unknown là gì?** Matched: dữ liệu thỏa comparator; unmet: có dữ
   liệu chứng minh không thỏa; unknown: thiếu/chưa đủ so sánh. RAM 8GB với yêu cầu
   16GB là unmet; camera chỉ có MP với “camera tốt” là unknown. Unknown và unmet
   không được cộng requirement points nhưng có ý nghĩa khác nhau.

9. **Snapshot giải quyết gì?** A chấm giá 15 triệu, B cập nhật offer 20 triệu thì GET
   A vẫn có giá/score/evidence cùng thời điểm. Comparison mới dùng cùng view đó.
   Legacy thiếu snapshot tính lại toàn bộ chỉ đọc, gắn semantics rõ, không backfill.
   Product detail vẫn đọc catalog hiện tại.

10. **Cache hoạt động thế nào?** SQLite cache qua abstraction, SHA-256 normalized
    requirement và config, TTL 1800 giây. Live session mới có thể copy complete
    snapshot hợp lệ; Demo không cache, rerun bỏ qua cache để refresh. Không sửa
    catalog hoặc tự cập nhật giá lịch sử. Chưa có job dọn cache hết hạn.

11. **Demo/Live khác gì?** Demo dùng sản phẩm giả lập và explanation local không cần
    key. Live dùng provider cấu hình và Tavily, có timeout/retry/fallback. LLM lỗi
    có local fallback; search lỗi không âm thầm trả sản phẩm Demo. Tests chưa xác
    minh key/model/API Live thật, vì dùng mock/Demo.

12. **History để làm gì?** Mở lại ngữ cảnh, trạng thái, snapshot và warnings. Đọc
    SearchSession cùng dữ liệu liên quan, không cần bảng history riêng. MVP local
    dùng chung DB, chưa phân quyền theo user.

13. **Comparison hoạt động thế nào?** Chọn 2–3 recommendation cùng session; kiểm
    tra ID/membership, lấy giá/spec/score từ một view và lưu bảng JSON. Winner theo
    score rồi rating/review count. Pros/cons lấy why_fit/tradeoffs đã lưu. Không có
    LLM comparison mới. Comparison cũ trước fix giữ nguyên; không thể phục hồi chắc
    chắn lịch sử thiếu bằng cách lấy dữ liệu hiện tại.

14. **Hạn chế?** Chất lượng phụ thuộc nguồn, extraction chưa tổng quát mọi website;
    rubric định tính và purpose là heuristic. Confidence chưa có freshness decay
    riêng; logging thiếu tracing đầy đủ; UI chưa có telemetry realtime. Docker chỉ
    kiểm tra tĩnh. Không tuyên bố production-ready hoặc giá luôn hiện hành.

15. **Hướng phát triển?** Xác minh Docker/Live, cải thiện extraction, calibration,
    freshness và observability; sau đó xét Voice, cá nhân hóa, price tracking,
    notifications, vector/hybrid search, feedback learning. PostgreSQL/Redis và
    deployment công khai cần validation/auth/vận hành riêng. Voice là Future Work.

## Câu hỏi mở rộng

- **AI nhận/trả gì?** Analyzer nhận câu tự nhiên, trả requirement có schema;
  explanation nhận requirement + candidate + score + evidence, trả narrative có
  schema. ID và dữ liệu số do backend cung cấp, không do AI tạo nguồn sự thật.
- **Sản phẩm ở đâu, vì sao Web Search?** Demo từ fixtures, Live qua Tavily và nguồn
  công khai. Search tìm dữ liệu biến động nhưng không bảo đảm đầy đủ/đúng lúc mua.
- **Search lỗi hết?** HTTP 503/FAILED, warnings bền vững, giữ kết quả thành công
  trước; cache chỉ dùng theo điều kiện hiện hữu. Có integration regression.
- **Tests có API trả phí?** Không. SQLite tạm, mocks/Demo; browser dùng local servers,
  keys rỗng và network guard.
- **DB/frontend làm gì?** DB giữ session/requirements, raw/sources, products/offers,
  recommendations/snapshots, comparisons, feedback, cache. UI nhận input/render,
  filter/sort và điều hướng; không tự suy diễn match/evidence hoặc đổi score.

## File nên mở khi giải thích

| Chủ đề | File |
|---|---|
| Công thức/comparator | backend/app/services/scoring/scoring_engine.py |
| Snapshot | backend/app/services/recommendation/recommendation_service.py |
| Evidence | backend/app/services/validation/structured_evidence.py |
| Comparison fix | backend/app/api/routes/comparison.py |
| Giá lịch sử | backend/tests/integration/test_recommendation_snapshot.py; test_comparison_api.py |
| Số liệu Demo | backend/tests/integration/test_demo_scenarios.py |
| Test DB sạch | backend/tests/conftest.py; backend/scripts/run_e2e_backend.py |
| Browser | frontend/e2e/; frontend/playwright.config.ts |

Đối chiếu kết quả thực và giới hạn trong [FINAL_AUDIT](FINAL_AUDIT.md).
