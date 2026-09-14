# Demo và kịch bản trình diễn

Chạy theo [README](../README.md), đặt `DEMO_MODE=true` trong `backend/.env`,
khởi động backend từ `backend/` và frontend từ `frontend/`. Không cần API key.
Mở `http://localhost:3000`; kiểm tra `/api/system/status` và nhãn Demo ở kết quả.
Dữ liệu dưới đây là sản phẩm giả lập, không phải báo giá mua hàng. URL `.example`
không phải website merchant thật để mở khi trình diễn.

Số liệu lấy từ `backend/tests/integration/test_demo_scenarios.py`. Tái lập:

```powershell
cd backend
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests/integration/test_demo_scenarios.py -v -s
```

Test chạy từng scenario trên schema SQLite tạm sạch. ID/timestamp thay đổi theo
lần chạy. `total_filtered` là số **được giữ lại**, không phải số bị loại. Cả ba
scenario hiện trả **3 candidates → 3 qua lọc → 3 recommendations**. TOP_K=5 không
sinh thêm sản phẩm để đủ năm.

## Quy trình 15 bước cho cả ba scenario

| Bước | Thao tác / điều cần chỉ ra |
|---|---|
| 1. Analysis | Dán nguyên văn câu bên dưới vào Home, gửi yêu cầu; xem category và requirements. |
| 2. Budget | Xác nhận budget_max đúng VND; budget_min của ba câu này là null. |
| 3. Purpose | Xem purpose trong Requirement Summary; không tự thêm thông số kỹ thuật từ purpose. |
| 4. Search | Gửi tìm kiếm; Python tạo query, MockSearchProvider trả dữ liệu. Xem `queries` trong response `/api/search` qua Network nếu cần. |
| 5. Candidates | Kiểm tra `total_found=3`. |
| 6. Hard filter | Kiểm tra `total_filtered=3`, category đúng, giá không vượt budget. |
| 7. Recommendation | Tới `/results/[sessionId]`, có ba sản phẩm được xếp hạng. |
| 8. AI Match | Xem score bên dưới và breakdown sáu thành phần với trọng số 25/30/20/10/5/10; Data Confidence là chỉ số riêng. |
| 9. Matching | Mở chi tiết: ✓ Đáp ứng / ✕ Không đáp ứng / ? Chưa đủ dữ liệu cùng giá trị/lý do backend trả. |
| 10. Evidence | Xem price/rating/review_count/specifications có nguồn, URL, thời điểm, reliability nếu có. Nguồn Demo là giả lập. |
| 11. Explanation | Xem tóm tắt, why_fit, tradeoffs/cautions; generation_mode là demo. |
| 12. Product detail | Mở `/products/[productId]`. Trang này đọc catalog hiện có; recommendation là snapshot. |
| 13. Comparison | Chọn 2–3 sản phẩm, mở `/compare/[comparisonId]`; giá/score lấy cùng view của session. Scenario test kiểm tra hai; suite comparison kiểm tra cả ba. |
| 14. Feedback | Gửi hữu ích/không phù hợp và lý do nếu cần. Feedback chỉ lưu, chưa huấn luyện mô hình. |
| 15. History | Xem lại đúng session; giá/score/evidence snapshot được giữ. Trình diễn filter/sort/reset trước khi rời kết quả. |

## 1. Tai nghe học online

> Tôi có 500 nghìn, cần tai nghe để học online, mic tốt, pin lâu.

Category `tai nghe`; budget_max **500000**; purpose `học online`; confidence
**0.95**. Requirements: microphone=`tốt` (priority 5), battery=`pin lâu` (priority 4).

| Rank | Sản phẩm Demo | Giá VND | Final score | Matching |
|---|---|---:|---:|---|
| 1 | SoundDemo H20 Wireless | 449000 | 92.44 | microphone ENC: matched; battery 40 hours: matched |
| 2 | LearnSound Pro | 499000 | 91.98 | microphone noise reduction: matched; battery 45 hours: matched |
| 3 | StudyBeat M5 | 399000 | 90.78 | microphone dual mic: matched; battery 35 hours: matched |

Kết quả 3/3/3. Microphone thỏa rubric Python hiện tại; đây không phải chất lượng
âm thanh được đo độc lập. Browser E2E dùng luồng Demo thực cho tai nghe từ Home
qua comparison, feedback và History.

## 2. Laptop học lập trình

> Tôi cần laptop khoảng 15 triệu để học lập trình.

Category `laptop`; budget_max **15000000**; purpose `học lập trình`; confidence
**0.85**; requirements **[]**.

| Rank | Sản phẩm Demo | Giá VND | Final score |
|---|---|---:|---:|
| 1 | CodeBook 15 | 14490000 | 92.45 |
| 2 | StudyPro L15 | 14900000 | 91.75 |
| 3 | DevNote 14 | 13990000 | 91.50 |

Kết quả 3/3/3. Câu này **không yêu cầu RAM cụ thể**. Không biến “học lập trình”
thành “RAM 16GB”. `requirement_matches=[]` là đúng; requirement score mặc định 100
khi không có explicit requirement không có nghĩa mọi khả năng laptop đã được chứng
minh. Specification/evidence vẫn hiển thị khi có; purpose score là heuristic riêng.

## 3. Điện thoại chụp ảnh và chơi game

> Tôi có 5 triệu, cần điện thoại để chụp ảnh và chơi game, ưu tiên camera tốt, pin lâu.

Category `điện thoại`; budget_max **5000000**; purpose `chơi game`, `chụp ảnh`;
confidence **0.95**. Requirements: battery=`pin lâu`, camera=`tốt`, cùng priority 5.

| Rank | Sản phẩm Demo | Giá VND | Final score | Matching |
|---|---|---:|---:|---|
| 1 | PixelDemo G8 | 4950000 | 93.33 | battery 4800mAh: matched; camera 50MP OIS: matched |
| 2 | DemoPhone X5 5G | 4790000 | 77.39 | battery 5000mAh: matched; camera 50MP: unknown |
| 3 | Nova Mobile A20 | 4490000 | 76.23 | battery 5100mAh: matched; camera 64MP: unknown |

Kết quả 3/3/3. **Số megapixel không đủ kết luận “camera tốt”**: unknown đúng hơn
matched hoặc unmet khi thiếu evidence. OIS là tín hiệu rubric đang hỗ trợ, không
phải cam kết chất lượng ảnh. Frontend không suy diễn để nâng điểm.

Câu này không thêm “không muốn máy quá nặng” của ví dụ mở rộng MASTER_SPEC; không
khẳng định đã phân tích ngưỡng trọng lượng chưa định lượng. Parser trọng lượng có
regression riêng. Hai scenario laptop/phone được kiểm tra qua integration API,
không được mô tả là ba hành trình browser đã chạy.

## Tình huống bổ sung và giới hạn

- Thử câu thiếu budget để trình diễn clarification; trả lời trước khi search.
- Filter/sort chỉ thay cách xem tập recommendation, không chấm lại điểm.
- Search lỗi toàn bộ trả lỗi, giữ snapshot cũ; dùng regression tests để chứng minh,
  không ngắt API thật khi bảo vệ. Hai browser fixtures kiểm tra metadata/status/URL.
- Nếu Live không hoạt động, bật Demo, restart backend và tạo session mới. Không
  gắn nhãn lại snapshot Live cũ thành Demo.
- AI Match là điểm 0–100, không phải xác suất hoặc bảo đảm chất lượng mua hàng.

Kết quả kiểm thử và giới hạn: [FINAL_AUDIT](FINAL_AUDIT.md).
