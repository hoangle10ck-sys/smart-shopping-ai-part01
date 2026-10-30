# Bản nháp báo cáo cho Overleaf

Các file trong `chapters/` là nội dung mới được soạn dựa trên mã nguồn/tài liệu Smart Shopping AI và checkpoint dự án ngày 30/10/2026. Đây là bản nháp để bạn đọc, hiệu chỉnh theo biểu mẫu khoa và ghép vào báo cáo hiện có; không chỉnh sửa `main.tex`, trang bìa, cam đoan, cảm ơn, tài liệu tham khảo hay chương hiện có của Overleaf.

## Ghép vào Overleaf

1. Tải các file trong `chapters/` lên đúng thư mục `chapters/` của dự án Overleaf.
2. So sánh nội dung với các file `chuong1.tex` đến `chuong7.tex` và `tomtat.tex` đang có. Hãy gộp thủ công nếu các file hiện hữu có nội dung cần giữ.
3. `main.tex` bạn cung cấp đã có `\include{chapters/tomtat}` và `\include{chapters/chuong1}` đến `\include{chapters/chuong7}`; nếu giữ nguyên tên, các file mới sẽ được đưa vào tài liệu khi biên dịch.
4. Chọn XeLaTeX trong Menu/Compiler của Overleaf vì main file dùng `fontspec`.
5. Kiểm tra lại số liệu, ngày checkpoint, cấu hình trường/khoa, hình minh họa và tài liệu tham khảo trước khi nộp.

## Giới hạn xác minh

- Nội dung mô tả implementation theo tài liệu repository tại checkpoint; không chỉnh sửa trực tiếp tài khoản Overleaf.
- Số test trong Chương 5 là kết quả được ghi nhận tại checkpoint 30/10/2026, không phải kết quả chạy mới của quá trình soạn file này.
- Kết quả audit ảnh là kiểm tra tự động bằng chứng/provenance/tính toàn vẹn; không phải kiểm duyệt trực quan thủ công toàn bộ ảnh.
- Báo cáo phân biệt dữ liệu Research, URL khám phá, offer được xác minh và trạng thái Live. Không dùng số liệu test để tuyên bố sản phẩm có giá/tồn kho thương mại hiện tại.
- Biên dịch XeLaTeX chưa được xác nhận trong môi trường repository này; hãy compile trong Overleaf và xử lý lỗi theo template của trường.
