# Spec — Tab Danh mục dev.atz.vn (port từ prod Streamlit)

- **Status:** Phase A–B shipped (2026-10-25); Phase C+ pending
- **Phạm vi:** `frontend/index.html` (`pb-ui:portfolio.*`), API FastAPI mới trong `backend/`
- **North star:** [ADR 0009](../adr/0009-dual-docker-spa-cutover.md) — sau cutover, cùng spec áp cho prod Docker; dev Docker validate trước khi promote.

---

## 1. Mục tiêu / non-goals

**Mục tiêu**

- Đưa giá trị **Danh mục / wl_rows / vị thế** từ prod Streamlit vào tab **Danh mục** SPA, realtime qua WS priceboard.
- Tái sử dụng logic Python prod (`watchlists_page`, `sidebar_portfolio`, `f3_alerts`, `capital_ledger`) qua **backend**, không nhân bản rule trong JS.

**Non-goals (phase đầu)**

- Telegram alert F3, full Trạm Trading UI, thay đổi nginx/Authentik compose.
- Gộp SQLite dev ↔ prod; sync tự động hai Docker.

---

## 2. Hiện trạng

| Khối prod (Streamlit) | Dev SPA hôm nay |
|------------------------|-----------------|
| `build_wl_symbol_rows` — Mã, Giá (Redis `quote:*` → OHLCV), KL TB 10, Cảnh báo F3 | Mã, SL, Giá TB, Giá TT, ±, %, P/L, KL ngày |
| Sidebar + `desk_position_rows`, `capital_ledger` | Chỉ NAV/P/L tổng; `localStorage` |
| `trading_desk` — hỗ trợ/kháng cự, tô màu F1 | Chưa có |

**Test tham chiếu:** `tests/test_watchlists_page.py`, `tests/test_sidebar_portfolio.py`, `tests/test_f3_alerts.py`, `tests/test_capital_ledger.py`.

**Dev data:** `localStorage` key `atz.app.portfolio`; WS `state` chung iBoard.

---

## 3. Quyết định đã chốt (open questions)

### Q1 — Cảnh báo: giá nào, hiển thị thế nào?

**Chốt: Hybrid (C), một cột «Cảnh báo».**

| Thành phần | Nguồn giá | Cập nhật |
|------------|-----------|----------|
| **F3** (xu hướng ngày, MA/BB/Ichimoku, thủng/vượt level) | **Close nến ngày** đã chốt (`bars_D`) | Refresh khi có bar ngày mới / lần mở tab / batch API; **không** re-run full F3 mỗi tick WS |
| **Intraday nhanh** | **Last RT** từ priceboard WS + **giá mua** (`avg`) | Theo tick; rule `position_alert` (±5/8/10%, gần hỗ trợ/kháng cự nếu có S/R) |

**UI:** Một chuỗi ghép ` · ` (F3 trước hoặc sau intraday — cố định trong impl, ghi trong PR).

Contract F3: [`F3_ALERTS.md`](F3_ALERTS.md).

### Q2 — Preset ngành F3

**Chốt: Merge + dedup** theo `symbol` (uppercase).

- Thêm mã từ `config/sector_themes_f3.yaml` **chưa có** trong danh mục.
- **Không** ghi đè `qty` / `avg` mã đã tồn tại.
- Phase sau (tuỳ chọn): nút **«Thay cả danh mục bằng ngành này»** + dialog xác nhận.

### Q3 — Persist & Authentik

**Chốt: D1** — Authentik **chung prod/dev** (đã ổn định); danh mục/vốn bền **SQLite** theo user ([ADR 0004](../adr/0004-trading-profile-sqlite-not-authentik.md), [0005](../adr/0005-data-placement-sqlite-redis.md)).

- Phase A–C: vẫn `localStorage`; API read-only không bắt buộc session.
- Phase D: FastAPI đọc identity từ header ForwardAuth (`X-authentik-*`); CRUD portfolio server-side; migrate một lần từ localStorage khi user login.
- **Dev DB ≠ prod DB**; cùng username, dữ liệu tách môi trường.

---

## 4. Phased delivery

### Phase A — UX desk nhẹ

- Tô màu P/L, giá TT vs giá TB ([`COLOR_TOKENS.md`](../COLOR_TOKENS.md), F1 mục 6).
- Cột **Cảnh báo** (client hoặc API): intraday `position_alert` khi đã có `avg` + last RT.

**AC:** Cùng input → cùng output band như `test_position_alert_bands_and_zones`.

### Phase B — Parity wl_rows (giá + thanh khoản)

- `GET /api/portfolio/quotes?symbols=...` — merge: hash priceboard → OHLCV → (optional read-only `quote:*` legacy).
- Cột **KL TB 10 phiên** (OHLCV).
- Đơn vị VND thống nhất SPA (`fmtPrice`).

**AC:** Tương đương `test_wl_rows_*` (server-side).

### Phase C — F3 + preset ngành

- `POST /api/portfolio/alerts` — engine `analysis/f3_alerts`.
- UI: chọn ngành F3 → **merge + dedup** mã.
- Cột **Cảnh báo** đủ Q1 (F3 + intraday).

**AC:** Smoke `tests/test_f3_alerts.py` trên fixture mã.

### Phase D — SQLite + user

- Endpoints CRUD danh mục (+ sau: `CapitalLedger` tóm tắt NAV).
- Middleware identity; migrate localStorage → server.

**AC:** `test_capital_ledger`, `test_rows_pnl_from_live_price` (logic backend).

---

## 5. API sketch

```text
GET  /api/portfolio/quotes?symbols=FPT,VIC
POST /api/portfolio/alerts        { "symbols": ["FPT"] }
GET  /api/portfolio/sectors/f3    → read-only từ sector_themes_f3.yaml

Phase D:
GET/PUT /api/portfolio/positions  (Authentik user scoped)
```

Auth: B public read phase B–C; D yêu cầu ForwardAuth (ADR 0003/0006).

---

## 6. Frontend

- Mở rộng item: `{ symbol, qty, avg, support?, resistance? }`.
- `patchPortfolioSymbol`: WS first; batch quotes cho mã thiếu tick.
- Catalog: `pb-ui:portfolio.*` trong `frontend/ui_catalog.json`.

---

## 7. Cutover prod (ADR 0009)

1. Parity checklist Pass trên **Docker dev**.
2. Promote git → **Docker prod** (nginx giữ nguyên).
3. Migrate SQLite user prod nếu cần.
4. Tắt Streamlit trong compose prod.

---

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|--------|------------|
| Đơn vị giá nghìn vs VND | Chuẩn hóa tại API |
| F3 CPU | Batch + cache theo symbol/ngày |
| FastAPI chưa đọc Authentik | Phase D blocker; nginx đã auth |

---

## 9. References

- [`F1_CHECKLIST_UI.md`](../F1_CHECKLIST_UI.md) (mục 2, 6)
- [`F3_ALERTS.md`](F3_ALERTS.md)
- [`ADR 0009`](../adr/0009-dual-docker-spa-cutover.md)
