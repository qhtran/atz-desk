# PROTOCOL — bắt buộc cho AuditorBot và Cursor

## 1. Phạm vi khảo sát

- **Production:** `https://atz.vn` (app VANTIQ / Streamlit sau auth nếu cần).
- **Đối chiếu:** `https://fireant.vn` (ít nhất `/thi-truong` và một trang mã, ví dụ `/ma-chung-khoan/VIC`).
- Không yêu cầu AuditorBot đọc source Python trừ khi bạn đính kèm snippet trong báo cáo.

## 2. Định dạng báo cáo

- Chỉ **Markdown** (`.md`), UTF-8.
- Bám `REPORT_TEMPLATE.md` (đủ các mục bắt buộc).
- Mỗi file = **một chủ đề** (colors, realtime board, news RSS, sidebar…). Không nhồi cả site vào một file khổng lồ nếu có thể tách.
- Ảnh: nếu computer use chụp được, lưu mô tả đường dẫn / URL ảnh **công khai** hoặc mô tả rõ «ảnh đính kèm không có trong repo». Không commit binary lớn trừ khi chủ repo đồng ý.

## 3. Git

- Branch gợi ý: `auditor/YYYYMMDD-<topic>` hoặc commit thẳng `main` nếu quy trình team cho phép (ưu tiên PR nhỏ).
- Path ghi: `docs/auditorbot/inbox/<filename>.md` thôi.
- Message gợi ý: `docs(auditor): <topic> vs FireAnt`.
- **Không** force push. **Không** đụng `.env`, secret, `deploy/` nginx/SSH.

## 4. Mức độ ưu tiên (dùng trong báo cáo)

| Tag | Nghĩa |
|-----|--------|
| `P0` | Sai / lệch nghiêm trọng (màu trần-sàn sai, dữ liệu sai, crash) |
| `P1` | UX bám bảng kém rõ (thiếu search, flash, đọc lướt) |
| `P2` | Nice-to-have (hover icon, T&S stream, pixel-perfect) |
| `BLOCKED` | Giới hạn nền tảng (vd. Streamlit `st.dataframe` không hover row) — ghi rõ, **không** đòi Cursor «làm giống Fireant bằng mọi giá» |

## 5. Phân loại lệch

Luôn ghi một trong hai (hoặc cả hai nếu hỗn hợp):

- **Thiếu sản phẩm** — chưa làm / thiếu dữ liệu / thiếu API.
- **Giới hạn Streamlit** — framework không hỗ trợ (hover row, global keydown mượt…).

## 6. Cursor sẽ làm gì với báo cáo

1. Đọc `inbox/*.md` mới nhất.
2. Trả lời user bằng `[DBG] intent=plan|ask` + lựa chọn đánh số.
3. Sau khi được chọn (hoặc theo workflow tự ship đã thống nhất): sửa code → test → merge `main` → deploy VPS.
4. Ghi **Resolution** vào cuối file rồi chuyển sang `reports/`.

## 7. Không làm

- Không yêu cầu Cursor lộ secret / sửa firewall.
- Không báo cáo kiểu «làm giống hệt Fireant» không có tiêu chí đo được.
- Không spam inbox (gộp lần survey cùng chủ đề trong ngày nếu có thể).
