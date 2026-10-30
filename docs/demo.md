# Mock fixtures lịch sử — chỉ dùng trong kiểm thử

Trang Home hiện luôn dùng automatic unified search. Không dùng hướng dẫn hoặc
bảng fixture trong tài liệu này để trình diễn như sản phẩm thật. `DEMO_MODE=true`
không khiến endpoint `/api/search` đưa `MockSearchProvider` vào kết quả unified;
fixture không có merchant/offer đang bán và URL `.example` không mở được như
website sản phẩm thật.

Test `backend/tests/integration/test_demo_scenarios.py` hiện xác nhận ba query
không nhận fixture giả khi catalog và nguồn web đều trống. Các bảng sản phẩm
bên dưới là ví dụ fixture lịch sử từ luồng cũ; test hiện tại không tạo hoặc trả
những record đó. Với Home, chỉ báo sản phẩm khi có catalog evidence hoặc nguồn
web được cấu hình, cho phép và xác minh.

Số liệu lấy từ `backend/tests/integration/test_demo_scenarios.py`. Tái lập:

```powershell
cd backend
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests/integration/test_demo_scenarios.py -v -s
```

Test chạy từng query trên schema SQLite tạm sạch. Search hợp nhất không có
catalog/provider nên kết quả hiện là **0 recommendations**; đây là bằng chứng
không bịa fixture, không phải bằng chứng nguồn Live hoạt động.

## Assertions của luồng hiện tại

| Bước | Thao tác / điều cần chỉ ra |
|---|---|
| Analysis | Test phân tích query và xác nhận category/requirement trên database tạm. |
| Budget / Purpose | Test các giá trị yêu cầu; không tự thêm thông số kỹ thuật từ purpose. |
| Search | Test pipeline mock/legacy để xác nhận query; đây không phải nguồn web và không chứng minh truy cập Live. |
| Candidates / filter / recommendation | Search không có dữ liệu hợp lệ trả 0 recommendations; không tự tạo đủ TOP_K. |
| Matching / Evidence | Kiểm tra schema/reasoning của pipeline; nguồn/URL trong fixtures là giả lập. |
| Explanation / detail / comparison | Các assertion kiểm tra nội dung snapshot và semantics của test; không phải sản phẩm có trang bán thật. |
| Feedback / history | Các test riêng kiểm tra persistence; không có dữ liệu này đại diện người dùng thật. |

## Ví dụ fixture lịch sử (đã ngừng sinh bởi test hiện tại)

Các bảng và điểm số còn lại bên dưới chỉ lưu dấu ví dụ tổng hợp của luồng cũ.
Chúng không phải catalog đang chạy, không phải kết quả lần test hiện tại và
không được dùng để chứng minh sản phẩm, offer hoặc giá thật.

## 1. Tai nghe học online

> Tôi có 500 nghìn, cần tai nghe để học online, mic tốt, pin lâu.

Category `tai nghe`; budget_max **500000**; purpose `học online`; confidence
**0.95**. Requirements: microphone=`tốt` (priority 5), battery=`pin lâu` (priority 4).

| Rank | Sản phẩm Demo | Giá VND | Final score | Matching |
|---|---|---:|---:|---|
| 1 | SoundDemo H20 Wireless | 449000 | 92.44 | microphone ENC: matched; battery 40 hours: matched |
| 2 | LearnSound Pro | 499000 | 91.98 | microphone noise reduction: matched; battery 45 hours: matched |
| 3 | StudyBeat M5 | 399000 | 90.78 | microphone dual mic: matched; battery 35 hours: matched |

Kết quả 3/3/3 thuộc ví dụ fixture lịch sử. Microphone thỏa rubric Python; đây
không phải chất lượng âm thanh được đo độc lập. Browser E2E hiện dùng catalog
tổng hợp riêng trên database tạm để kiểm tra unified UX; nó không gọi
`DemoProductSource` hoặc `MockSearchProvider`.

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
- Nếu nguồn web không khả dụng, kiểm tra provider/policy và xem trạng thái nguồn
  trong kết quả. Không bật fixture để giả lập kết quả mua hàng hoặc gắn nhãn lại
  snapshot cũ thành Demo/Live.
- AI Match là điểm 0–100, không phải xác suất hoặc bảo đảm chất lượng mua hàng.

Kết quả kiểm thử và giới hạn: [FINAL_AUDIT](FINAL_AUDIT.md).
