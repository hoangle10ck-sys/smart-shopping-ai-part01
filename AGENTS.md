AGENTS.md — Smart Shopping AI
Quy tắc vận hành chung dành cho Codex và các AI coding agent trong repository smart-shopping-ai-part01.
Phạm vi: toàn repository. Quy tắc chuyên biệt ở thư mục con (ví dụ frontend/AGENTS.md) được áp dụng bổ sung, miễn không xung đột với các giới hạn an toàn và quyết định của chủ dự án.

1. Mục tiêu và phạm vi quyền
- Tiếp tục hoàn thiện hệ thống trợ lý mua hàng thông minh, nơi người dùng truy cập không cần đăng nhập, nhập nhu cầu bằng ngôn ngữ tự nhiên, nhận đề xuất sản phẩm và so sánh giá dựa trên bằng chứng thực.
- Tái sử dụng code và dữ liệu hiện có. Không xây dựng lại dự án, tạo hệ thống song song, hoặc đổi kiến trúc/luồng nghiệp vụ chỉ để phù hợp với ví dụ hay tài liệu cũ.
- Có thể chủ động phân tích, lập kế hoạch, sửa code trong nhiệm vụ đã được giao/phê duyệt, thêm hoặc cập nhật test liên quan và chạy kiểm thử an toàn. Không coi danh sách backlog là sự cho phép tự động triển khai mọi đề xuất tùy chọn.
- Đối với yêu cầu chỉ audit/đánh giá/chẩn đoán, chỉ được đọc và báo cáo; không chỉnh sửa file, tạo báo cáo trong repo hoặc thay đổi trạng thái nhiệm vụ nếu chưa được yêu cầu.
2. Bất biến không được tự ý thay đổi
1. Kiến trúc: Bảo toàn cấu trúc FastAPI/Python, Next.js/TypeScript và các module, API, cơ chế snapshot, cache, scoring, nguồn dữ liệu hiện có. Không đổi framework, thiết kế module, API contract, cơ chế phân quyền hay mô hình dữ liệu nếu chưa được duyệt.
2. Luồng nghiệp vụ: Giữ định hướng tìm kiếm đa nguồn tự động: người dùng mô tả nhu cầu, hệ thống tìm nguồn nội bộ và nguồn ngoài đã tích hợp, cấu hình, được phép, trong ngân sách vận hành. Không yêu cầu người dùng bật từng sàn/chế độ như điều kiện bắt đầu. Giữ khả năng tương thích với các luồng cũ khi còn được sử dụng. Nếu thiếu sản phẩm, chỉ thu thập từ nguồn hợp lệ; không cam kết bao phủ toàn Internet.
3. Tính trung thực dữ liệu: Không bịa sản phẩm, giá, tồn kho, ưu đãi, đánh giá, URL hoặc nguồn. Không trình bày fixture/Demo hay dữ liệu research lịch sử là offer Live hiện tại. Ghi nhận provenance, thời gian quan sát, mức độ xác minh, cảnh báo thiếu dữ liệu và partial failure.
4. An toàn thu thập: Tuân thủ điều khoản và quyền truy cập từng nguồn, robots/policy và giới hạn tốc độ, timeout, concurrency. Không vượt CAPTCHA, anti-bot, xác thực, endpoint nội bộ không được phép hoặc dùng proxy/stealth né chặn. Thiếu quyền hoặc không truy cập được phải báo đúng trạng thái.
5. Dữ liệu và bí mật: Không xóa/đặt lại database, không chạy migration phá hủy (migrate:fresh, db:wipe, reset/drop/truncate hoặc tương đương), không sửa .env, lộ credentials hay thay đổi dữ liệu production. Migration mới hoặc thay đổi schema cần phân tích tác động và phê duyệt; không tự suy diễn phải chuyển SQLite sang PostgreSQL hay ngược lại. Cấu hình thực tế có thể khác nhau giữa local và Docker Compose.
6. Git và triển khai: Không ghi đè thay đổi chưa commit; không tự ý reset/clean, force push, push, merge, release, deploy hoặc commit khi chưa được yêu cầu. Không xóa file vì tưởng là code thừa trước khi kiểm tra tham chiếu và cách gọi động.
7. Dependencies: Không tự cài thêm thư viện, đổi major version hoặc thay provider/LLM mặc định nếu chưa được phê duyệt. Không gọi API có phí hoặc live crawl trong quá trình test mặc định.
3. Nguồn tài liệu và xử lý mâu thuẫn
Đọc các tài liệu có tồn tại và liên quan đến nhiệm vụ:
Vai trò	Nguồn tham khảo
Điểm vào và cách chạy	README.md
Đặc tả nghiệp vụ	docs/MASTER_SPEC.md (lưu ý PROJECT OVERRIDES đối với phần spec gốc)
Kiến trúc hiện hành	docs/architecture.md, docs/api.md, docs/database.md
Quy trình kiểm thử	docs/testing.md
Collector track	TASKS.md, docs/CRAWLER_RUNBOOK.md, docs/collector-policy.md
Research track	TASKS_RESEARCH_DATA.md
Unified Search	TASKS_UNIFIED_SEARCH.md
Frontend/UI	UI_TASKS.md, frontend/AGENTS.md
Tổng quan tiến độ	MISS.md; checkpoint chi tiết thuộc từng task/progress file
Ngữ cảnh liên phiên	memory-bank/ và CLAUDE.md khi phù hợp với agent đang chạy


- Quyết định mới nhất được người dùng phê duyệt và các ràng buộc an toàn có ưu tiên hơn suy luận từ tài liệu cũ. PROJECT OVERRIDES xử lý xung đột bên trong MASTER_SPEC.md; không mặc nhiên thay thế mọi quyết định khác.
- Mã nguồn và test hiện hành là bằng chứng về implementation, không tự động phủ quyết yêu cầu nghiệp vụ. Tài liệu lịch sử và báo cáo test phải được hiểu theo ngày/checkpoint của chúng.
- Khi hai quy tắc thực sự xung đột hoặc không rõ nguồn có thẩm quyền: dừng phần bị ảnh hưởng, nêu file/mục/dòng, tác động và các phương án; hỏi chủ dự án. Không âm thầm chọn một bên.
- Không sửa/tẩy xóa lịch sử cũ để làm số liệu nhất quán. Phân biệt trạng thái DONE đã nghiệm thu, implementation mới chỉ đọc code, test offline, dữ liệu historical và Live đã xác minh.
4. Quy trình thực thi mỗi nhiệm vụ
1. Khảo sát: Xem git status, cấu trúc liên quan, chỉ dẫn agent, task/checkpoint và code/test hiện tại. Nếu công cụ terminal báo lỗi hoặc completion không xác minh được, ghi nhận giới hạn; không giả lập output thành công.
2. Chọn phạm vi: Ưu tiên tiếp tục task đang dở trong phạm vi được giao, kiểm tra dependency, điều kiện nghiệm thu, file liên quan và ảnh hưởng tới luồng cũ. Thông báo ngắn gọn mục tiêu và kế hoạch trước khi thay đổi đáng kể.
3. Thực hiện tối thiểu: Theo convention dự án; tái sử dụng thành phần hiện có; không refactor rộng hoặc tối ưu ngoài phạm vi. Xử lý input, lỗi và tình huống thiếu nguồn/thiếu bằng chứng minh bạch.
4. Kiểm thử: Chạy targeted tests trước, rồi regression/lint/build thích hợp nếu môi trường cho phép. Unit/integration test mặc định phải offline, không request trả phí hoặc live crawl. Không nói PASS nếu chưa chạy hoặc chưa quan sát được mã thoát đáng tin cậy.
5. Cập nhật tiến độ: Chỉ đánh dấu [x]/DONE khi đáp ứng Definition of Done có bằng chứng. Bảo toàn checklist và checkpoint cũ; cập nhật đúng file task của track nếu việc cập nhật thuộc phạm vi đã được giao. MISS.md chỉ tổng hợp và dẫn nguồn, memory-bank/ chỉ ghi ngữ cảnh ngắn, không tạo checklist song song.
6. Báo cáo: Nêu task, thay đổi, file, test/lệnh/kết quả, vấn đề còn tồn tại, giới hạn xác minh, bước tiếp theo và phần cần phê duyệt.
5. Cổng phê duyệt bắt buộc
Dừng và xin duyệt trước nếu phương án cần một trong các hành động sau:
- Thay đổi kiến trúc, API contract, schema/database, cơ chế xác thực, luồng nghiệp vụ hoặc logic tính điểm/chọn sản phẩm đã được chốt.
- Thêm/bỏ dependency, nâng major version, đổi AI/search provider, bật Live collector hoặc làm phát sinh phí.
- Xóa/gộp/di chuyển tài liệu có thể chứa quy tắc, bằng chứng hoặc lịch sử; xóa code/module; refactor liên module.
- Thao tác với dữ liệu thực, migration, secrets, Git remote hoặc triển khai môi trường ngoài local.
- Mở rộng công việc ngoài nhiệm vụ được giao hoặc giải quyết mâu thuẫn tài liệu chưa rõ thẩm quyền.
Mẫu đề xuất:
NEEDS_APPROVAL
Vấn đề và bằng chứng (file/dòng):
Thay đổi đề xuất và vì sao cần:
Phương án giữ nguyên / phương án thay thế:
Module, API, database, dữ liệu chịu tác động:
Tương thích ngược, rủi ro và cách khôi phục:
Kiểm thử và tiêu chí nghiệm thu:
Quyết định cần người dùng xác nhận:
Không xem việc trình bày đề xuất là quyền triển khai. Có thể tiếp tục các task độc lập, an toàn và đã được giao trong lúc chờ quyết định.
6. Quy tắc theo khu vực
- Frontend: Đọc và tuân thủ frontend/AGENTS.md. Nếu Next.js yêu cầu đọc tài liệu phiên bản hiện cài tại frontend/node_modules/next/dist/docs/, hãy làm trước khi chỉnh sửa phần liên quan. Không xóa khối chỉ dẫn do next dev tạo tự động chỉ để làm sạch Git diff.
- Backend/Database: Tôn trọng dialect và cấu hình runtime thực tế; phân biệt SQLite local, PostgreSQL Compose nếu đúng với configuration kiểm tra được. Không giả định một báo cáo cũ phản ánh DB đang chạy.
- Collector/Research/Live: Giữ rõ danh tính Product/Variant/Offer, snapshot bất biến, provenance, freshness và khả năng so sánh SKU. Các nhãn FIXTURE_TESTED_ONLY, HISTORICAL_RESEARCH, LIVE_NOT_VERIFIED, ACCESS_RESTRICTED không được tráo đổi.
7. Tiêu chuẩn hoàn thành
Một nhiệm vụ chỉ được xem là hoàn thành khi: yêu cầu và phạm vi được đáp ứng; chức năng liên quan được kiểm tra; không có regression đã biết chưa báo cáo; dữ liệu/nguồn được mô tả trung thực; task/checkpoint cập nhật đúng khi được phép; mọi hạn chế chưa xác minh được nói rõ.

Mục tiêu cuối cùng: Chủ động hoàn thiện kế hoạch được giao, nhưng mọi thay đổi lớn phải có lý do, bằng chứng và được chủ dự án phê duyệt. Không phá vỡ kiến trúc, nghiệp vụ, dữ liệu hoặc quy tắc hiện hành.

8. Quyền hạn và thứ tự áp dụng quy tắc
- Tuânatuân thủ các chỉ dẫn có hiệu lực cao hơn và yêu cầu mới nhất của người dùng, trong phạm vi an toàn và được phép. Bảo toàn quyết định nghiệp vụ, kiến trúc và tiêu chí nghiệm thu đã được người dùng phê duyệt.
- AGENTS.md gốc quy định vận hành chung cho repository. AGENTS.md ở thư mục con chỉ bổ sung quy tắc chuyên biệt; không được nới lỏng giới hạn an toàn hoặc vượt quyết định đã được phê duyệt.
- CLAUDE.md và hướng dẫn do IDE/extension sinh ra chỉ áp dụng cho agent/công cụ tương ứng; nội dung tự sinh không tự động trở thành yêu cầu nghiệp vụ của dự án.
- Không lấy trạng thái mã nguồn hiện tại làm căn cứ để hủy bỏ hoặc thay thế yêu cầu nghiệp vụ đã được phê duyệt. Nếu thẩm quyền giữa các tài liệu chưa rõ, dừng phần bị ảnh hưởng và hỏi người dùng.

9. Chế độ READ-ONLY
- Trong nhiệm vụ audit, review, chẩn đoán hoặc được yêu cầu READ-ONLY: chỉ đọc và báo cáo. Không sửa code, TASKS, MISS, Memory Bank, database, cấu hình hoặc tài liệu; không tạo file/artifact trong repository; không chạy thao tác có tác dụng phụ ngoài phạm vi đọc.
- Không cập nhật trạng thái nhiệm vụ hoặc tài liệu tiến độ trong READ-ONLY. Đề xuất thay đổi không đồng nghĩa với quyền thực hiện.

10. Quyền triển khai nhiệm vụ
- Backlog và checklist mô tả kế hoạch, không tự cấp quyền triển khai tất cả mục. Chủ động hoàn thành phần nằm trong nhiệm vụ người dùng đã giao/phê duyệt, đúng phạm vi và điều kiện nghiệm thu.
- Không tự mở rộng phạm vi, thay mục tiêu hoặc tiêu chí nghiệm thu, hay triển khai mục đang chờ phê duyệt. Nếu phát sinh công việc ngoài phạm vi, nêu riêng và hỏi người dùng.

11. Trạng thái kiểm chứng và kết quả lệnh
- Dùng các nhãn riêng biệt: CODE_INSPECTED (đã đọc source/config, chưa chứng minh hoạt động); OFFLINE_TESTED (kiểm thử offline đã chạy và kết quả được xác nhận); LIVE_VERIFIED (đã xác minh Live theo quyền nguồn, tiêu chí và bằng chứng); NOT_RUN (chưa chạy); UNVERIFIED (đã thử nhưng chưa xác nhận được kết quả).
- Không đánh đồng các trạng thái trên hoặc suy ra PASS từ việc đọc code, output hiển thị, fixture hay mã thoát do shell in ra.
- Chỉ báo lệnh thành công khi executor xác nhận tiến trình hoàn tất và exit code đáng tin cậy. Nếu không quan sát được completion hoặc exit code mâu thuẫn, ghi UNVERIFIED; không báo PASS và không lặp lệnh tương tự nếu chưa có phương pháp/bằng chứng mới.

12. Cập nhật Memory Bank và tài liệu tiến độ
- Chỉ cập nhật Memory Bank khi được giao/cho phép và có thông tin ngắn gọn, hữu ích cho phiên sau, đã được xác minh. Không điền placeholder chỉ để hoàn thành hình thức; không sao chép checklist vào Memory Bank.
- TASKS là nguồn checklist và tiêu chí nghiệm thu chi tiết theo track; MISS là tổng hợp tiến độ và dẫn đến nguồn chi tiết; Memory Bank lưu ngữ cảnh ngắn. Không dùng các nguồn này thay thế lẫn nhau.
- Khi được phép cập nhật tiến độ, giữ lịch sử/checkpoint; ghi rõ ngày, phạm vi, bằng chứng và trạng thái kiểm chứng. Không xóa nội dung cũ chỉ để làm số liệu nhất quán.

13. Kiểm thử theo phạm vi
- Ưu tiên targeted tests, sau đó chạy regression/lint/build phù hợp với phạm vi và rủi ro. Tuân thủ nguyên vẹn tiêu chí nghiệm thu đã được phê duyệt; không hạ tiêu chí để báo hoàn thành.
- Nếu không thể chạy kiểm thử đã yêu cầu, ghi NOT_RUN cùng lý do và giới hạn. Không thực hiện Live, API trả phí hoặc tác vụ có tác dụng phụ trừ khi được phép theo phạm vi và cổng phê duyệt.

14. Phê duyệt thay đổi lớn
- Phải xin phê duyệt trước khi thay đổi kiến trúc, luồng nghiệp vụ, API contract, database schema, logic scoring/ranking, chính sách thu thập dữ liệu, dependency/công nghệ; refactor diện rộng hoặc xóa module quan trọng.
- Đề xuất cần nêu: (1) vấn đề và bằng chứng; (2) lý do; (3) phương án giữ nguyên; (4) phương án nâng cấp; (5) lợi ích; (6) rủi ro/tác động; (7) tương thích ngược; (8) kế hoạch kiểm thử và khôi phục.
- Chỉ triển khai phương án được người dùng chấp thuận rõ ràng. Các cổng phê duyệt tại mục 5 vẫn áp dụng.