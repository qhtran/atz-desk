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
   - `datasource/`: lấy dữ liệu. Không dùng tên `data/` cho code vì `data/` là cache trên volume.
   - `analysis/`: canslim, technical, patterns, screening.
   - `ui/`: các thành phần giao diện, charts.
   - `app.py` chỉ điều hướng.
3. Đơn giản hóa biểu đồ: nến chính rõ (MA + Bollinger), các chỉ báo khác để trong expander.
4. Thêm Dashboard đơn giản (trạng thái thị trường + Top 20). Có trang Dashboard trong `app.py` và trang `dashboard.py` cùng nội dung đó. Trang một mã không còn nằm ở `dashboard.py`. `app.py` chọn trang bằng thanh ngang. Chỉ trang đang chọn được tính, nên Dashboard không tải biểu đồ và CANSLIM.

## Tiêu chí hoàn thành (Definition of Done)
- [x] Các giá trị hardcode chính đã chuyển vào config.py
- [x] app.py không còn chứa logic phân tích dài
- [x] Biểu đồ nến là phần nổi bật, chỉ báo phụ có thể thu gọn
- [x] Có view/tab Dashboard (trạng thái phiên + Top 20)
- [x] App khởi động không lỗi
- [x] Đã commit và push

## Cách kiểm tra
- Chạy `streamlit run app.py` và mở được trang chính
- Xem được biểu đồ của một mã (ví dụ POW)
- Top 20 vẫn hiển thị ở tab Dashboard
- Chạy `streamlit run dashboard.py` và thấy trạng thái phiên cùng bảng Top 20
- Không có traceback trong log

## Lưu ý
- Pull trước khi sửa.
- Làm từng phần nhỏ và commit.
- Giữ nguyên logic lọc Top 20 hiện tại.
- Tuân thủ AGENTS.md.
