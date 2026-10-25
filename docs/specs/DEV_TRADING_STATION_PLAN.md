# Plan — Trạm Trading / QLTS trên DEV (dev.atz.vn)

**Status:** P1–P4 implement trên `feature/realtime-fastapi` · `/trading` + `/api/trading/*`  
**Ngày:** 2026-10-25 (cập nhật sau implement)  
**Phạm vi:** chỉ DEV — `backend/`, `frontend/`, `docker-compose.dev.yml`  
**UI demo duyệt:** `frontend/demo-final.html` (trace label `demo-ui-final`)  
**PR demo:** https://github.com/qhtran/quanlychungkhoan/pull/5  

---

## Đã chốt

| Mục | Quyết định |
|-----|------------|
| Site | **DEV** (`dev.atz.vn`) — không prod |
| UI | Theme board hiện tại; demo HTML đã phê duyệt |
| Bán nhiều tranche | **Avg cost** (giá TB vàng) — không FIFO phase 1 |
| Fee / tax | Brokerage **0.15%**; thuế bán **0.1%** → YAML |
| Max tranche | **5** (T1–T5) |
| Giá live | Redis hash `priceboard:quotes` field `last` |
| Trace | `X-Request-ID` + JSON `{error_code, trace_id, message}` |
| Identity MVP | Header `X-authentik-username` hoặc `default_user` trong YAML |

---

## Cấu trúc đích

```text
backend/
  main.py
  core/
    database.py
    redis_client.py
    logging_middleware.py
    errors.py
  modules/
    trading/     # models, schemas, repository, service, router
    assets/      # phase P5 — vốn / sổ đọc transactions
config/trading_station.yaml
tests/test_trading_station.py
tests/test_logging_middleware.py
frontend/demo-final.html   # mock duyệt → nối API ở P4
```

---

## Schema SQLite

- **`positions`:** user+symbol, status open/closed, qty, avg_buy_price, invested, realized_pnl, sl, tp_json  
- **`trade_transactions`:** side BUY/SELL, tranche 1..5, qty, price, fee, tax, ts, note  

DB path đề xuất: `data/dev_trading.db` (volume compose DEV).

---

## API (P3)

Prefix `/api/trading`:

| Method | Path |
|--------|------|
| GET | `/positions` |
| GET | `/positions/{id}` |
| POST | `/buy` |
| POST | `/sell` |
| PATCH | `/positions/{id}/levels` |
| POST | `/positions/{id}/close` |

Chuông: `last ≤ sl` → `sl`; `last ≥ tp_i` → `tp`; else `idle`.

---

## Thứ tự PR

| PR | Việc | Pass |
|----|------|------|
| **P1** | `core/` DB + middleware + errors; mount `main.py` | middleware tests; `/healthz` 200 |
| **P2** | `modules/trading` models/repo/service + unit tests | avg/fee/tax Pass (không cần Redis) |
| **P3** | router + Redis last + volume DB | curl buy/list + PnL |
| **P4** | FE nối API (thay mock trong demo / tab) | network có `X-Request-ID` |
| **P5** | `modules/assets` stub + sổ từ transactions | tab QLTS |

---

## Open (chưa chọn số trong chat)

- FE gắn: tab trong `index.html` **vs** page `trading.html` riêng (demo hiện file riêng).  
- Assets: P5 riêng **vs** gộp sớm.

Mặc định đề xuất nếu chat mới không có chọn: **tab/`trading.html` từ demo** · Assets = **P5**.

---

## Non-goals (slice này)

- Không đụng iBoard/Screener logic trừ mount router.  
- Không nginx / Authentik / SSH.  
- Không ghi `idx:quote:*`.  

---

## Merge → `main` (deploy dev.atz.vn)

1. PR `feature/realtime-fastapi` → `main` (resolve conflict với priceboard depth nếu có).  
2. `./scripts/check-dev.sh --pytest-only` (gồm `test_trading_station`, `test_logging_middleware`).  
3. `./scripts/deploy-vps.sh dev` — verify `https://dev.atz.vn/trading` + header `X-Request-ID` trên `/api/trading/positions`.
