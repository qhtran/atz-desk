# Checklist chỉnh sửa site — lần F1 (mentor)

- **Nguồn:** `MoTaCongViecThucHienCapNhatSite_RevF1.docx` (iCloud StockRnD / ideas_from_Hien)
- **Bản chữ + ảnh local:** cùng thư mục, file `*_text.md` và `*_media/word/media/`
- **Ngày ghi checklist:** 2026-10-17
- **Trạng thái:** Chưa triển khai code (chỉ ghi nhận yêu cầu)

---

## 1. Đặt tên thương hiệu

- [ ] Chọn / áp dụng tên (gợi ý mentor: **VANTIQ** = Vietnam + Analytics + IQ)
- [ ] Slogan gợi ý: *Think in Data. Trade with Discipline.*
- [ ] Cập nhật chỗ hiện tên trên UI (title, header…); hiện đang kiểu “Quét thị trường” / atz

**Ảnh tham chiếu:** `image1.png`

---

## 2. Sidebar: “Phiên và vốn” → “Tổng quan vị thế của bạn”

Thay khối hiện tại (trạng thái phiên + tổng vốn + mức rủi ro %) bằng tổng quan tài khoản / vị thế:

- [ ] Vốn rót lần đầu
- [ ] Vốn bổ sung
- [ ] Vốn đã rút ra
- [ ] Tổng vốn hiện tại
- [ ] Giá trị chứng khoán
- [ ] Tiền mặt
- [ ] Tài sản ròng
- [ ] Vị thế hiện tại — từng **thương vụ**: mã / giá mua / giá hiện tại / cảnh báo
- [ ] Giá hiện tại realtime (tham chiếu sàn UBCK: https://rtboard.hsx.vn/)
- [ ] Cảnh báo theo ưu tiên: hỗ trợ 1–2, kháng cự 1–2, và/hoặc mốc ±5% / ±8% / ±10%
- [ ] Biểu đồ cột lãi/lỗ trên tổng NAV (phía dưới)

**Ảnh tham chiếu:** `image3.png` (hiện trạng) + mô tả cột “Đề xuất sửa” trong doc

**Độ lớn:** lớn (UI + lưu dữ liệu user)

---

## 3. Bảng “Chỉ số Việt Nam” — cột mũi tên phiên

- [ ] **Xóa chữ** tiêu đề cột 「Mũi tên」(giữ chỗ hiển thị hình)
- [ ] Thay icon tam giác hiện tại bằng **mũi tên phiên**:
  - Đường ngang **vàng** = tham chiếu
  - Đường nối từ cao → thấp, đầu mũi tên ở **giá đóng cửa**
  - **Xanh** nếu tăng, **đỏ** nếu giảm
- [ ] Thu hẹp độ rộng cột; chữ header 2–3 hàng nếu cần để vừa nhiều cột

**Ảnh tham chiếu:** `image4.png`, `image5.png` (mẫu mũi tên), `image6.png` (khoanh xóa/sửa)

---

## 4. Thu hẹp cột khối lượng / bảng chỉ số

- [ ] Làm hẹp cột kiểu 「Tổng KL khớp (triệu CP)」và các cột liên quan để nhìn được nhiều dữ liệu hơn trong một khung
- [ ] (Theo chú thích UI) làm rõ nguồn: giá/KL vs giá trị khớp / thỏa thuận

**Ảnh tham chiếu:** `image7.png`  
**Tham khảo ngoài (mentor):** https://www.hsx.vn/ · https://fireant.vn/dashboard/ · https://vietstock.vn/

**Độ lớn:** nhỏ–vừa (chủ yếu CSS/layout)

---

## 5. Top mã khối lượng tích cực trong phiên

- [ ] Lọc / hiển thị **20 mã** có khối lượng giao dịch tăng mạnh nhất so với **TB 10 phiên**
- [ ] Điều kiện: TB 10 phiên **≥ 500.000** (500k)
- [ ] Phân biệt với Top 20 ROE/thanh khoản hiện có (nếu giữ cả hai thì đặt tên rõ)

**Ảnh tham chiếu:** `image8.png` (bảng Top hiện tại — cần đổi logic/nhãn cho đúng yêu cầu KL phiên)

**Độ lớn:** lớn (logic lọc mới + có thể nguồn dữ liệu mới)

---

## 6. Tô màu bảng “Quản trị vị thế”

- [x] Cột **Lãi/lỗ**: lãi chữ xanh, lỗ chữ đỏ
- [x] Cột xu hướng → **xu hướng ngày**: tăng xanh / giảm đỏ
- [x] Cột **Giá mua**: **nền vàng** cả cột (chữ tối cho dễ đọc)
- [x] Cột **Giá hiện tại**: cao hơn giá mua = xanh; thấp hơn = đỏ
- [x] **Vùng hỗ trợ**: số màu đỏ
- [x] **Vùng kháng cự**: số màu xanh

**Ảnh tham chiếu:** `image9.png`, `image10.png` (đủ cột hỗ trợ / kháng cự / 1/4 NAV / cắt lỗ…)

**Độ lớn:** nhỏ–vừa (chủ yếu trình bày)  
**Code:** `src/atz/ui/trading_desk.py` (`style_desk_board`) — 2026-10-17  
**Màu chuẩn:** `src/atz/ui/theme_tokens.py` + `docs/COLOR_TOKENS.md` (FireAnt-style, áp cả Tổng quan / Realtime)

---

## 7. “Bộ lọc tín hiệu” — thêm Tiêu chí lọc

- [ ] Giữ / làm rõ tab **Bộ lọc tín hiệu**
- [ ] Bổ sung mục **Tiêu chí lọc** (bảng):

| TT | Tên tiêu chí | Ghi chú trong doc F1 |
|----|--------------|----------------------|
| I | Chỉ tiêu kỹ thuật | |
| 1 | Nến Nhật | Đảo chiều tại hỗ trợ; mạnh / TB / yếu / 3 đáy (chi tiết trong doc) |
| 2 | RSI | 2–3 đáy vùng 30, vượt đáy trung tâm |
| 3 | MACD | Cắt lên Signal + histogram cải thiện ≥ 2 phiên |
| 4 | Các đường MA | Yếu / mạnh / rất mạnh theo MA5/10/20/50 |
| 5 | Bollinger | *(chưa mô tả trong bản F1 đã convert)* |
| 6 | Mây Ichimoku | *(chưa mô tả)* |
| II | Chỉ báo mẫu hình | *(doc bị cắt — cần mentor bổ sung)* |

**Ảnh tham chiếu:** `image11.png` (tab)

**Độ lớn:** lớn; **thiếu nội dung** mục 5–6 và phần II

---

## Gợi ý thứ tự làm (chưa bắt buộc)

1. Mục 6 (tô màu) — nhanh, ít rủi ro  
2. Mục 3 + 4 (mũi tên + hẹp cột) — thấy rõ trên Tổng quan  
3. Mục 1 (tên) — branding  
4. Mục 2 / 5 / 7 — làm từng phần, có thiết kế + xác nhận trước khi code  

---

## Việc chưa làm trong checklist này

- Triển khai code / deploy VPS  
- Merge đầy đủ phần tài liệu mentor bị cắt (Bollinger, Ichimoku, mẫu hình)  
