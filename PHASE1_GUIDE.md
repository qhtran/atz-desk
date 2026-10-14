# Hướng dẫn Giai đoạn 1: Nền tảng & Dọn dẹp

## Mục tiêu
- Code modular, dễ bảo trì.
- Giao diện biểu đồ đỡ rối.
- Có config tập trung.
- Có Dashboard cơ bản.
- App vẫn chạy được sau khi thay đổi.

## Phạm vi làm
1. Chuẩn hóa config.py (đưa ngưỡng ROE, volume, watchlist, tham số chỉ báo vào đây).
2. Tách module theo hướng:
   - data/ : lấy dữ liệu
   - analysis/ : canslim, technical, patterns, screening
   - ui/ : các thành phần giao diện, charts
   - app.py chỉ điều hướng
3. Đơn giản hóa biểu đồ: nến chính rõ (MA + Bollinger), các chỉ báo khác để trong expander.
4. Thêm Dashboard đơn giản (trạng thái thị trường + Top 20).

## Tiêu chí hoàn thành (Definition of Done)
- [ ] Các giá trị hardcode chính đã chuyển vào config.py
- [ ] app.py không còn chứa logic phân tích dài
- [ ] Biểu đồ nến là phần nổi bật, chỉ báo phụ có thể thu gọn
- [ ] Có view/tab Dashboard
- [ ] App khởi động không lỗi
- [ ] Đã commit và push

## Cách kiểm tra
- Chạy app và mở được trang chính
- Xem được biểu đồ của một mã (ví dụ POW)
- Top 20 vẫn hiển thị
- Không có traceback trong log

## Lưu ý
- Pull trước khi sửa.
- Làm từng phần nhỏ và commit.
- Giữ nguyên logic lọc Top 20 hiện tại.
- Tuân thủ AGENTS.md.
