# Tech Journal — ATZ Desk (dev.atz.vn)

Nhật ký ngắn cho thay đổi **kiến trúc / logic** quan trọng (bảo dưỡng + debug sau này).  
Không thay ADR; không dump changelog dài. Mỗi mục: ngày · phạm vi · quyết định · file neo · follow-up.

---

## 2026-11-04 — P0 Master Catalog + Quote Snapshot (off-core)

**Phạm vi:** Desk priceboard search / Quick Switcher — mã ngoài Core WS (~80 `default_watchlist`), chưa dynamic SSI subscribe.

**Quyết định**
- Catalog = merge runtime: `board_universe` + F3 themes + `config/market_catalog.json` (overlay tên/exchange).
- Core flag = `config/priceboard_core_symbols.yaml` (rỗng → `default_watchlist()`), soft cap 240.
- Snapshot resolve: Redis `priceboard:quotes` → OHLCV CSV → stub catalog (`priced: false`). **Không** mở WS topic mới ở P0.
- FE Switcher: `GET /api/catalog/symbols?q=` rồi `GET /api/quotes/snapshot?symbols=` hydrate `state` trước khi mở panel.

**API**
- `GET /api/catalog/symbols?q=&limit=`
- `GET /api/catalog/symbol/{symbol}`
- `GET /api/quotes/snapshot?symbols=`

**File neo**
- `backend/market_catalog.py`, `backend/quote_snapshot.py`, `backend/routers/catalog.py`
- `config/market_catalog.json`, `config/priceboard_core_symbols.yaml`
- `frontend/index.html` (switcher suggest)
- `tests/test_market_catalog.py`
- Commit: `b0f0cdf`

**Smoke đã xác nhận (VPS desk-dev)**
- `DBC` catalog `in_core=false`; snapshot `ohlcv` có giá; `FPT` snapshot từ priceboard `in_core=true`.

**Follow-up (lúc viết P0)**
- P1: dynamic SSI subscribe khi add watchlist/portfolio.
- Core YAML điền Top 240 liquidity rank thật (EOD job).
- Đồng bộ listing SSI → refresh `market_catalog.json` định kỳ.

---

## 2026-11-04 — P1 Core Top 240 + On-Demand SSI subscribe

**Phạm vi:** desk-dev Core stream mở rộng; worker dynamic SUBSCRIBE/UNSUBSCRIBE.

**Quyết định**
- `config/priceboard_core_symbols.yaml`: **240 mã** (VN30 ∪ F3 ∪ midcap ladder ∪ HNX/UPCOM liquid). DBC nằm trong Core.
- Redis hash `priceboard:ondemand` (field=symbol, value=unix touch). Idle mặc định **30 phút**, max **40** mã off-core.
- API: `POST /api/priceboard/watch` · `GET /api/priceboard/ondemand`.
- Watchlist create/update → `touch_ondemand_symbols`.
- FE Switcher/hydrate → POST watch (kể cả khi đã có snapshot).
- `ssi_live`: static subscribe = **`load_core_symbol_set()`** (Top 240 YAML), không còn chỉ `default_watchlist()` ~80.
- `ssi_live`: poll 5s, SUBSCRIBE mã mới / UNSUBSCRIBE hết hạn; reconnect hydrate ondemand vào topic set.

**File neo**
- `config/priceboard_core_symbols.yaml`
- `backend/ondemand_watch.py`, `backend/ssi_live.py`, `backend/routers/catalog.py`, `backend/routers/watchlist.py`
- `frontend/index.html` (`touchPriceboardWatch`)
- `tests/test_ondemand_watch.py`
- Journal rule: `.cursor/rules/tech-journal.mdc`

**Chưa làm**
- EOD job rank thanh khoản thật (thay curated ladder).
- Unsubscribe khi user xóa mã khỏi mọi watchlist (hiện chỉ idle TTL).
- Portfolio Desk add-symbol → watch (có thể reuse cùng API).

---

## 2026-11-04 — PROD release atz.vn (Desk :8001)

**Phạm vi:** Promote P0+P1 catalog/core/ondemand lên **atz.vn** (prod-desk). `user_confirmed_infra: yes`. Không đụng legacy `/opt/vnstocks`.

**Thực thi**
- Tip: `e742ae3`
- VPS `/opt/atz-desk`: `./scripts/deploy-prod-desk.sh` + `docker compose -f docker-compose.prod-desk.yml --profile live up -d --build ssi-worker`
- Containers: `atz-desk-api` :8001 healthy · `atz-ssi-worker` · `atz-redis-desk-prod`

**Verify**
- Worker: `X-Quote topics: 242` (Top 240 + HĐTL) · DATA topics ~1222
- API: catalog `DBC` `in_core=true`
- Browser `https://atz.vn`: Switcher DBC → quote live **15,750 · +3.62%** (`snap_source=priceboard`)

**Ghi chú ops**
- `deploy-prod-desk.sh` mặc định **không** bật `--profile live`; recreate SSI worker phải gọi riêng với profile `live`.

---

## 2026-11-05 — F3 ngành: pills ngang + popover

**Phạm vi:** FE Portfolio picker ngành F3 (atz Desk SPA). Không đổi API `/api/portfolio/sectors/f3` hay bảng 5 cột.

**Quyết định**
- Accordion dọc `#pf-f3-themes` chiếm viewport → thay bằng thanh **pills** `overflow-x:auto` + **một popover** (đóng: X / backdrop / Escape / click pill lại).
- Giữ `hydrateF3Sector`, `ensureF3Alerts`, `data-pf-add-one`, `data-f3-open`, `data-atd-id` sector.

**File neo**
- `frontend/index.html` — CSS `.pf-f3-pills` / `.pf-f3-popover`, `openF3Pill` / `closeF3Popover`
- `tests/test_portfolio_f3.py` — `test_f3_pills_popover_markup`

**Follow-up**
- P2: neo popover theo pill đang chọn (anchor) nếu panel hẹp trên mobile.
