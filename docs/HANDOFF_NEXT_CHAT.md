# Handoff — ATZ Desk (dev.atz.vn)

**Cập nhật:** 2026-10-27  
**Repo:** [atz-desk](https://github.com/qhtran/atz-desk) · VPS dev clone **`/opt/atz-desk`**  
**Deploy:** `./deploy-dev` (hoặc `./scripts/deploy-vps.sh dev` / trên VPS `./scripts/deploy-vps.sh dev-local`)

## Ai đọc file này

- **Master (ag1):** trạng thái sản phẩm khi lập task mới.
- **Executor (ag2):** không đọc file này nếu packet không trỏ một mục.
- Mỗi turn: [`docs/agents/NOW.md`](agents/NOW.md). Archive `docs/agents/archive/` — không mở.

---

## Phạm vi owner

- **Active:** **ATZ Desk** — `dev.atz.vn` — `backend/`, `frontend/`, `docker-compose.dev.yml` (project `atz_desk`, container `atz-desk-api-dev`)
- **Legacy prod:** `/opt/vnstocks` (Streamlit, ingestion) — ngoài scope dev trừ ops seed OHLCV
- **Một bảng iBoard** — lọc ngày = subset trên cùng `#board-table`

---

## Đã ship (gần nhất)

| Commit / epic | Nội dung |
|---------------|----------|
| **LWC + panel phân tích** | Chart FireAnt-style: nến daily, range 1d–5y, MA10/50, marker filter; `equity_spark` + `symbol-intraday` |
| **Rebrand ATZ Desk** | Repo `atz-desk`, `./deploy-dev`, nginx `atz-desk-api-dev`, glossary vnstock vs Desk |
| **Filters P1** | Multi-filter daily, bollinger/adx/…, `rs_index`, `market_regime`, … |
| **`6fe7f21`** | P1 prep depth HĐTL (partial tick, depth-only publish) |
| **`7ae3da5`** | OHLCV EOD seed: `backend/ohlcv_seed.py`, `./scripts/seed-iboard-ohlcv.sh` |
| **`2e9ee5d`** | Daily UX, Top 20 KL, cột CV cố vấn |

**Spec chart:** [`docs/specs/IBOARD_MODULE_MAP.md`](specs/IBOARD_MODULE_MAP.md)

---

## iBoard — cách dùng

1. **Live WS** — bảng theo tab (kể cả **VN30F1M/F2M**, **Khối ngoại**).
2. **Tín hiệu ngày** — Quét trên OHLCV `data/ohlcv/*.csv`.
3. **Phân tích mã** — cột XHT / click mã → panel LWC + sidebar filter (marker trên daily ≥3m).
4. **Preset 1d** — intraday phiên (`equity_intraday_1m` + spark); marker filter chỉ daily.

**API (chart):** `GET /api/iboard/symbol-bars?range=`, `symbol-filter-history`, `symbol-intraday`

---

## Ops dev VPS

| Mục | Chi tiết |
|-----|----------|
| **Deploy** | Laptop: `./deploy-dev` · VPS: `cd /opt/atz-desk && ./scripts/deploy-vps.sh dev-local` |
| **Nginx** | `./scripts/apply-dev-atz-nginx.sh` (auto sau deploy dev) |
| **Branch** | `scripts/deploy-vps.env` → `ATZ_VPS_BRANCH=main` |
| **Mount** | `data/ohlcv` (ro api), `data/market.db`, symlink từ `/opt/vnstocks/data` nếu cần |
| **OHLCV EOD** | `./scripts/seed-iboard-ohlcv.sh` — ưu tiên `python3 -m backend.ohlcv_seed` nếu có vnstock; else container `vnstocks` |
| **Cron gợi ý** | Sau **15:05 VN** các ngày giao dịch: `cd /opt/atz-desk && ./scripts/seed-iboard-ohlcv.sh --market HOSE` (tuần 1 lần `--market ALL`) |
| **Verify data** | `curl 'http://127.0.0.1:8000/api/iboard/symbol-bars?symbol=VIC&range=1y'` → bars; `POST daily-signals` HOSE → `scanned>0` |

---

## Việc tiếp (sprint A→B→C)

| Phase | Trạng thái | Ghi chú |
|-------|------------|---------|
| **A** Ops + OHLCV | Done trong sprint | HANDOFF + seed path Desk |
| **B** Chart 1d đủ | Done trong sprint | Nến 1m + refresh WS + UX frozen |
| **C** HĐTL depth phiên | Checklist | Xem [`docs/agents/REMIND_2026-10-26_HDL_DEPTH.md`](agents/REMIND_2026-10-26_HDL_DEPTH.md) — verify **trong giờ 9–15 VN** |

Khác (backlog): prod cutover ADR 0009, CapitalLedger, filter intraday.

---

## Test local

```bash
./scripts/check-dev.sh              # pytest + docker healthz + API smoke (filters + symbol-bars)
./scripts/check-dev.sh --pytest-only
```
