# Handoff — priceboard dev (chat tiếp theo)

**Cập nhật:** 2026-10-25  
**Nhánh:** `main` + commit mới: **iBoard Tín hiệu ngày** (toolbar, không tab riêng)  
**Deploy:** `dev.atz.vn` — `./scripts/deploy-vps.sh dev --push`

---

## Phạm vi owner

- **Active:** `dev.atz.vn` — `backend/`, `frontend/`, `docker-compose.dev.yml`
- **Không** phát triển prod Streamlit / cutover prod trừ khi owner mở lại (ADR 0009)
- **Một bảng iBoard** — không thêm tab/bảng giá trùng; lọc ngày = subset trên cùng board

---

## Đã ship (Danh mục + cutover docs)

| Commit (gần nhất) | Nội dung |
|-------------------|----------|
| `6228f95` | Phase D — Authentik + SQLite `portfolio.db` |
| `f3f4329` | Phase C — F3 alerts + ngành merge |
| `41b7489` | Phase B — quotes + KL TB 10 |
| `f70195c` | Phase A — desk styling + intraday |
| `6921198` | ADR 0009 + spec `PORTFOLIO_DEV_FROM_PROD.md` |

**API Danh mục:** `GET/PUT /api/portfolio/positions`, `POST .../migrate`, `GET /api/account/me`, quotes, F3 alerts, sectors/f3.

---

## iBoard — hướng lọc (owner chốt)

- **Không** khôi phục tab 「Bộ lọc tín hiệu」riêng.
- **Tín hiệu ngày** (OHLCV + `filters/*`) → toolbar iBoard, chế độ **Live WS | Tín hiệu ngày**, cùng `#board-table`.
- Realtime: toolbar % / KL / trần-sàn (FilterEngine) — giữ nguyên ở chế độ Live.

**API:** `POST /api/iboard/daily-signals` `{ market, filter }` → `symbols[]` (rsi | macd | ma).  
**UI:** Nguồn **Live WS | Tín hiệu ngày** → **Quét** → subset trên cùng `#board-table`.

---

## Việc tiếp (gợi ý)

1. **Advisor scoring 0–100** — `docs/specs/FILTER_SCORING_HUONG1.md`
2. **Mở rộng daily signals** — thêm filter (candle, volume, foreign), cache theo ngày
3. **Top 20 / Top KL phiên** — subset “Áp lên iBoard” (không bảng mới)
4. **Parity checklist** — doc trước cutover prod (ADR 0007)
5. **CapitalLedger / NAV** — optional trên Danh mục

---

## Prompt gợi ý chat mới

```text
Đọc docs/HANDOFF_NEXT_CHAT.md + FILTER_SCORING_HUONG1.md.
dev.atz.vn only. Tiếp [advisor score | daily signals mở rộng | Top 20 subset iBoard].
```

---

## Ops dev VPS

- `PRICEBOARD_SOURCE=ssi` trên worker khi có cred
- Mount: `data/ohlcv`, `data/portfolio.db` (API)
- F3 engine trong image: `atz_pkg/analysis` (Dockerfile.dev)
