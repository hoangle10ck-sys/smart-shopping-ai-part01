# Mẫu đề nghị quyền truy cập Live marketplace

Tài liệu này là mẫu để chủ dự án gửi cho Shopee/Lazada hoặc đối tác được ủy quyền.
Nó không phải là giấy phép truy cập và không tự thay thế hợp đồng/điều khoản của sàn.

## 1. Thông tin bên đề nghị

- Pháp nhân/cá nhân:
- Mã số doanh nghiệp hoặc thông tin định danh:
- Người liên hệ kỹ thuật:
- Người liên hệ pháp lý/bảo mật:
- Website/app chính thức:
- Quốc gia triển khai: Việt Nam

## 2. Mục đích và phạm vi

Smart Shopping AI giúp người dùng tìm và so sánh sản phẩm. Chúng tôi đề nghị quyền
truy cập chính thức để đọc thông tin sản phẩm công khai hoặc API được cấp phép, phục vụ
hiển thị kết quả có provenance và liên kết về marketplace.

Không thực hiện: đăng nhập người dùng, mua hàng tự động, CAPTCHA solving, bypass WAF,
reverse-engineer API nội bộ, proxy rotation, fingerprint bypass hoặc thu thập ngoài
domain/API được phê duyệt.

## 3. Dữ liệu đề nghị được phép đọc

Chỉ xin các trường cần thiết, tùy API/feed mà sàn chấp thuận:

| Nhóm | Trường |
|---|---|
| Identity | product ID, shop ID, SKU/variant ID, tên, brand, model |
| Offer | listed price, sale price, currency, availability |
| Fulfillment | shipping fee/estimate, voucher summary nếu được phép |
| Trust | seller rating, review count nếu được phép và phải giữ provenance |
| Policy | warranty/return text nếu API/feed cung cấp |
| Link | canonical product URL và attribution/affiliate link được cấp |

Không suy diễn field bị thiếu; giá range phải giữ là range, không biến thành giá SKU cụ thể.

## 4. Tần suất và bảo vệ hệ thống

- Tối đa: `[N]` URL/request mỗi phút, `[N]` request đồng thời mỗi host.
- Chỉ truy vấn khi người dùng yêu cầu hoặc theo feed/cache được phê duyệt.
- Tôn trọng quota, Retry-After, robots/policy và mọi giới hạn trong hợp đồng.
- Có circuit breaker, timeout, body limit 2 MB, log mã trạng thái không chứa cookie/token.
- Dữ liệu lưu tối đa `[N]` ngày; hỗ trợ xóa dữ liệu khi được yêu cầu.
- Không lưu credential trong source control; dùng secret manager/env runtime.

## 5. Đề nghị sàn xác nhận bằng văn bản

Vui lòng xác nhận:

1. Kênh/API/feed chính thức và tài liệu kỹ thuật áp dụng.
2. Các domain, endpoint, field và mục đích được phép.
3. Quota, rate limit, cache/freshness và yêu cầu attribution.
4. Thời hạn, khu vực áp dụng, điều kiện thu hồi và đầu mối hỗ trợ.
5. Yêu cầu bảo mật, bảo vệ dữ liệu và hợp đồng/DPA (nếu có).

## 6. Quy trình nội bộ sau khi được duyệt

1. Lưu văn bản chấp thuận, ngày hiệu lực, scope và quota trong hồ sơ vận hành ngoài git.
2. Cập nhật `docs/collector-policy.md` và ghi rõ nguồn/bằng chứng.
3. Cấu hình secret runtime; bật đồng thời `COLLECTOR_LIVE_ENABLED` và
   `COLLECTOR_POLICY_CONFIRMED` ở môi trường riêng.
4. Smoke một URL sản phẩm công khai, một sàn mỗi lần, ở rate thấp.
5. Kiểm tra status, identity, variant, price type, freshness, provenance và persistence.
6. Ghi `LIVE_VERIFIED` hoặc `ACCESS_RESTRICTED` theo từng sàn; tắt flag nếu smoke thất bại.

## 7. Mẫu tiêu đề email

`Đề nghị cấp quyền API/feed sản phẩm cho Smart Shopping AI — [Tên pháp nhân]`

Đính kèm: mô tả use case, architecture/security note, danh sách field, quota dự kiến,
website/app, thông tin pháp nhân và đầu mối kỹ thuật/pháp lý.
