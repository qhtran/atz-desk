# iBoard priceboard — bản đồ module (dev.atz.vn)

**Mục đích:** Tra cứu nhanh *sửa ở đâu* — agent/human **@ file này** thay vì quét repo.  
**Phạm vi:** FastAPI priceboard (`backend/`, `frontend/index.html`, `config/priceboard.yaml`).  
**Prod Streamlit:** ngoài bảng này trừ khi user mở lại phạm vi prod.

---

## Luồng dữ liệu (1 dòng)

`SSI WS / mock worker` → `tick_contract.build_tick` → Redis `priceboard:quotes` + pub → `redis_listener` → WS `/ws/priceboard` → `frontend/index.html` (`state` Map → lọc tab → bảng).

---

## Bảng tra cứu theo chủ đề

| Chủ đề | File chính | Hàm / vùng | Test / spec liên quan |
|--------|------------|------------|------------------------|
| **Tab sàn UI** (HOSE, VN30, HNX, UPCOM, HĐTL, Khối ngoại) | `frontend/index.html` | HTML `.mkt-tab` `data-market`; JS `marketTab`, `setMarketTab()`, `VALID_MARKETS` | — |
| **Lọc dòng theo tab** | `frontend/index.html` | `matchesMarketTab()`, `rowVisible()`, `applyBoardFilter()` | — |
| **Gán sàn cho dòng** | `frontend/index.html` | `resolveExchange(row)` | — |
| **Rổ mã theo tab (BE)** | `backend/board_universe.py` | `symbols_for_market_tab()`, `exchange_for_symbol()`, `default_watchlist()` | `tests/test_board_universe.py` |
| **Danh sách mã hardcode (VN30 / HOSE thêm / HNX / UPCOM)** | `backend/board_universe.py` | `VN30_SYMBOLS`, `HOSE_EXTRA_SYMBOLS`, `HNX_SYMBOLS`, `UPCOM_SYMBOLS` | `tests/test_board_universe.py` |
| **Bản sao hardcode FE (drift risk)** | `frontend/index.html` | `VN30_SET`, `HNX_SET`, `UPCOM_SET` (phải khớp BE) | — |
| **Subscribe SSI / hydrate Redis** | `backend/ssi_live.py` | `RealSsiWorker.symbols`, `_build_topics()`, `_load_board_from_redis()`, `_bootstrap_rest()`, `_merge_tick()`, `_publish()` | `config/priceboard.yaml` → `ssi.*`, `rest_bootstrap`; REST: `backend/ssi_rest_bootstrap.py` |
| **Mock worker** | `backend/ssi_worker.py` | `build_seed()`, `_tick_row()`, `MockSsiWorker` | `config/priceboard.yaml` → `source: mock` |
| **Parse SSI → field tick** | `backend/tick_contract.py` | `parse_ssi_envelope()`, `build_tick()`, `tick_has_payload()` | `tests/test_tick_contract.py` |
| **Hợp đồng JSON tick** | `backend/tick_contract.py` | `build_tick()` — `exchange`, `foreignBuy`, `foreignSell`, depth | `tests/test_tick_contract.py` |
| **Lọc KL tối thiểu (ẩn mã)** | `backend/volume_filter.py` | `VolumeFilterSettings`, `load_volume_filter_settings()`, `passes_volume_filter()` | `tests/test_volume_filter.py` |
| **WS snapshot + fan-out** | `backend/redis_listener.py` | `load_snapshot()`, `merge_index_stubs()` | — |
| **WS endpoint** | `backend/main.py` | `@app.websocket("/ws/priceboard")` | `docs/specs/PRICEBOARD_DEBUG.md` |
| **Index bar (VN-INDEX, VN30, …)** | `frontend/index.html` | `INDEX_ORDER`, `applyIndex()`, `fetchIndexSpark()`, spark theo trục phiên VN | `GET /api/iboard/index-spark` ← `backend/index_spark.py` + `data/market.db` |
| **Cột depth 3 bước** | `frontend/index.html` | `applyEquity()`, `enrichDepth()`, cột `data-f=bid*`, `ask*` | `docs/specs/PRICEBOARD_P1_DEPTH_NN.md` |
| **Cột ĐTNN (6 — SSI)** | `frontend/index.html` | KL: `fbuy`,`fsell`,`fnet`; GT: `fbuyv`,`fsellv`,`fnetv`; tab Khối ngoại: `matchesForeignLiveRow()` | `tick_contract._parse_foreign_fields` (bq/sq/bv/sv) + `room.{sym}` |
| **Tín hiệu ngày / quét rổ** | `backend/daily_signals.py` | `scan_daily_signals()`, `symbols_for_market_tab(market)` | `backend/main.py` → `/api/iboard/daily-signals` |
| **Config runtime** | `config/priceboard.yaml` | `min_volume`, `min_volume_by_exchange`, `ssi.channels`, `ssi.symbols` | ENV `PRICEBOARD_*`, `SSI_*` |
| **Debug overlay / ui_ref** | `frontend/debug-overlay.js`, `frontend/ui_catalog.json` | `pb-ui:iboard.market.*`, `pb-ui:iboard.equity.row.*` | `docs/specs/PRICEBOARD_DEBUG.md` |

---

## Tab sàn — quy tắc hiện tại (tóm tắt)

| Tab | Điều kiện hiển thị dòng (FE) | Nguồn mã subscribe (BE mặc định) |
|-----|------------------------------|-----------------------------------|
| **HOSE** | `resolveExchange(row) === "HOSE"` | `VN30_SYMBOLS` + `HOSE_EXTRA_SYMBOLS` (+ mã synthetic mock) |
| **VN30** | `VN30_SET.has(symbol)` | Cùng 30 mã `VN30_SYMBOLS` |
| **HNX** | `resolveExchange(row) === "HNX"` | `HNX_SYMBOLS` (15 mẫu) |
| **UPCOM** | `resolveExchange(row) === "UPCOM"` | `UPCOM_SYMBOLS` (15 mẫu) |
| **VN30F1M / F2M** | Chỉ đúng 1 mã HĐTL | Index topics + 1 dòng depth |
| **Khối ngoại** | Mọi mã trong rổ, live: `foreignBuy > foreignSell` | `symbols_for_market_tab("FOREIGN")` = full watchlist |

**Lưu ý:** Tab HOSE **gồm cả** mã VN30 (union theo sàn), không trừ VN30 — khác tab VN30 (chỉ 30 mã).

---

## ĐTNN — field trong contract

| Layer | Field | Ghi chú |
|-------|--------|---------|
| Parse SSI | `fBuyVol`, `fSellVol`, `BuyForeignQtty`, `SellForeignQtty`, `foreignBuy`, `foreignSell` | `tick_contract.parse_ssi_envelope` |
| Tick JSON | `foreignBuy`, `foreignSell`, `foreignBuyValue`, `foreignSellValue`, `foreignNetVol` | GT parse từ SSI; FE hiển thị 3 cột KL (Mua/Bán/Ròng) |
| Subscribe | `ssi_live._build_topics` | `room.{SYMBOL}` cho room ngoại |

---

## Khi sửa — checklist ngắn

1. Đổi rổ mã → **cả** `board_universe.py` **và** `frontend/index.html` (3 Set).  
2. Đổi lọc tab → `matchesMarketTab` + `resolveExchange` (FE).  
3. Đổi subscribe SSI → `config/priceboard.yaml` / `ssi_live.py` `DEFAULT_SYMBOLS`.  
4. Đổi parse/merge tick → `tick_contract.py` + `ssi_live._merge_tick`.  
5. ĐTNN / depth → `PRICEBOARD_P1_DEPTH_NN.md` + test `test_tick_contract.py`.

---

**P0 (2026-10-25):** `ssi_live._merge_tick` truyền `exchange=exchange_for_symbol(sym)`; FE `resolveExchange` ưu tiên `HNX_SET`/`UPCOM_SET` trước field `exchange`; `applyEquity` luôn gán `row.exchange = resolveExchange(row)`.

**P1 (2026-10-25):** `min_volume_by_exchange` — HOSE 500k, HNX/UPCOM 50k (`volume_filter.VolumeFilterSettings`).

*Cập nhật: 2026-10-25 — audit routing sàn + ĐTNN + P0 exchange + P1 min_volume.*
