# Checklist chỉnh sửa site — lần F1 (mentor)

- **Nguồn:** `MoTaCongViecThucHienCapNhatSite_RevF1.docx` (iCloud StockRnD / ideas_from_Hien)
- **Bản chữ + ảnh local:** cùng thư mục, file `*_text.md` và `*_media/word/media/`
- **Ngày ghi checklist:** 2026-10-17
- **Trạng thái:** F1 UI gần xong (1–7 catalog/MVP); còn siết logic filter F1 + realtime giá sidebar

---

## 1. Đặt tên thương hiệu

- [x] Chọn / áp dụng tên: **VANTIQ** = Vietnam + Analytics + IQ
- [x] Slogan: *Think in Data. Trade with Discipline.*
- [x] Cập nhật title/header app (`ui/brand.py` + `app.py`); domain/auth vẫn atz.vn

**Ảnh tham chiếu:** `image1.png`  
**Code:** 2026-10-17 — chưa kèm logo SVG (chỉ chữ)

---

## 2. Sidebar: “Phiên và vốn” → “Tổng quan vị thế của bạn”

Thay khối hiện tại (trạng thái phiên + tổng vốn + mức rủi ro %) bằng tổng quan tài khoản / vị thế:

- [x] Vốn rót lần đầu
- [x] Vốn bổ sung
- [x] Vốn đã rút ra
- [x] Tổng vốn hiện tại
- [x] Giá trị chứng khoán (ước lượng theo vốn phân bổ desk)
- [x] Tiền mặt
- [x] Tài sản ròng
- [x] Vị thế hiện tại — mã / giá mua / giá hiện tại / cảnh báo (từ Trạm Trading)
- [x] Giá hiện tại realtime tick HSX (Redis `quote:{symbol}` → nghìn đồng; fallback OHLCV; link rtboard.hsx.vn) — 2026-10-17
- [x] Cảnh báo: gần hỗ trợ/kháng cự + mốc ±5/8/10%
- [x] Biểu đồ cột lãi/lỗ ước lượng trên NAV phân bổ

**Ảnh tham chiếu:** `image3.png` (hiện trạng) + mô tả cột “Đề xuất sửa” trong doc

**Độ lớn:** lớn (UI + lưu dữ liệu user)  
**Code:** `datasource/capital_ledger.py` + `ui/sidebar_portfolio.py` — 2026-10-17 (MVP)

---

## 3. Bảng “Chỉ số Việt Nam” — cột mũi tên phiên

- [x] **Xóa chữ** tiêu đề cột 「Mũi tên」(giữ chỗ hiển thị hình)
- [x] Thay icon tam giác hiện tại bằng **mũi tên phiên** (SVG):
  - Đường ngang **vàng** = tham chiếu
  - Đường nối từ cao → thấp, đầu mũi tên ở **giá đóng cửa**
  - **Xanh** nếu tăng, **đỏ** nếu giảm (token FireAnt)
- [x] Thu hẹp độ rộng cột; chữ header ngắn / 2 hàng

**Ảnh tham chiếu:** `image4.png`, `image5.png` (mẫu mũi tên), `image6.png` (khoanh xóa/sửa)  
**Code:** `src/atz/ui/session_arrow.py` + `overview_page.py` — 2026-10-17

---

## 4. Thu hẹp cột khối lượng / bảng chỉ số

- [x] Làm hẹp cột KL/GT (nhãn ngắn + `width="small"`)
- [x] Caption nguồn dữ liệu giữ nguyên / bổ sung chú thích mũi tên

**Ảnh tham chiếu:** `image7.png`  
**Tham khảo ngoài (mentor):** https://www.hsx.vn/ · https://fireant.vn/dashboard/ · https://vietstock.vn/

**Độ lớn:** nhỏ–vừa (chủ yếu CSS/layout)

---

## 5. Top mã khối lượng tích cực trong phiên

- [x] Lọc / hiển thị **20 mã** có KL phiên / TB 10 phiên trước cao nhất
- [x] Điều kiện: TB 10 phiên **≥ 500.000** (500k)
- [x] Tách tên với Top 20 ROE/thanh khoản (expander riêng trên Tổng quan)

**Ảnh tham chiếu:** `image8.png`  
**Code:** `analysis/volume_leaders.py` + `overview_page.show_volume_leaders` — 2026-10-17  
**Nguồn:** OHLCV local (sau Quét); chưa tick realtime phiên

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

- [x] Giữ / làm rõ tab **Bộ lọc tín hiệu**
- [x] Bổ sung mục **Tiêu chí lọc** (catalog UI, map sang filter hiện có)
- [ ] Siết logic filter đúng mô tả F1 (nến đảo chiều / RSI đáy / MACD hist…)
- [ ] Bollinger / Ichimoku / phần II — chờ mentor bổ sung doc

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
**Code:** `ui/filter_criteria.py` + expander trên `filters_page` — 2026-10-17

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
