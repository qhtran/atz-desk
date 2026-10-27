# Intent — iBoard F3 (dev.atz.vn)

## Mục tiêu cuối

Trên **ATZ Desk / iBoard** (`dev.atz.vn`), người dùng mở **danh mục cổ phiếu theo nhóm ngành** dạng **accordion (cây)**. Mỗi ngành mở ra bảng **5 cột**:

1. **Danh sách mã** — symbols trong theme F3  
2. **Giá realtime** — last / % đổi (WS / quotes hiện có)  
3. **Đồ thị** — spark / chart intraday thu nhỏ  
4. **Cảnh báo kỹ thuật** — MA (20/50/100/200), Bollinger, Ichimoku, hỗ trợ–kháng cự  
5. **Bài viết / Cộng đồng** — Phase 1 stub (“sắp có”)

## Hiện trạng (gap)

| Đã có | Chưa có / lệch Mentor F3 |
|-------|--------------------------|
| `config/sector_themes_f3.yaml` (14 theme ngành + symbols) | Accordion cây 5 cột |
| `GET /api/portfolio/sectors/f3`, `POST /api/portfolio/alerts` | Alert đang **wrap** `analysis.f3_alerts` (legacy `src/` / `atz_pkg`); workspace có thể không có package → runtime fail |
| Panel chip F3 + preview hẹp trong `frontend/index.html` | UI Mentor: accordion + 5 cột đầy đủ |
| Filter screener `ma` / `bollinger` (`daily_signals`) | Worker F3 riêng (MA20/50/100/200 + BB + Ichimoku + S/R) |
| Intraday / equity-spark API iBoard | Cột cộng đồng thật (CMS) |
| Paper trading (`trading.html`, `/api/trading/*`) | Không dùng cho bảng ngành F3 |

## Phạm vi

- **Trong:** `backend/`, `frontend/`, `config/` (active dev `dev.atz.vn`)  
- **Ngoài:** `src/` legacy, paper-trading module, prod atz.vn, CMS cộng đồng thật, force-recalc alert mỗi tick WS

## Mặc định thiết kế (đã chốt)

1. UI F3 gắn **iBoard** trong `frontend/index.html` (thay/mở rộng `#pf-f3-*`), không dùng `trading.html`.  
2. Cột Cộng đồng Phase-1 = stub.  
3. Logic cảnh báo = **native** trong `backend/` (OHLCV CSV + YAML sector); giữ contract HTTP gần endpoint hiện tại.

## Done khi

- Accordion F3 render từ themes YAML  
- Giá RT gắn kênh quotes/WS sẵn có  
- Alert daily native, cache theo `(symbol, session_date)`  
- Cột 5 stub ổn định  
- Có test module tương ứng (`tests/test_portfolio_f3.py` hoặc tương đương) — thực hiện ở Bước 3–4

## Cửa dừng SDLC

Bước 1–2: chỉ `intent.md` + `spec.md`. **Chờ duyệt `spec.md`** trước khi viết `plan.md` / code production.
