# Handoff — priceboard dev (chat tiếp theo)

**Cập nhật:** 2026-10-25  
**Nhánh deploy VPS:** `main` — commit **`acf4361`** (advisor + iBoard daily)  
**Deploy:** `./scripts/deploy-vps.sh dev` (hoặc `--push` trước khi deploy)

## Ai đọc file này

- **Master (ag1):** trạng thái sản phẩm khi lập task mới.
- **Executor (ag2):** không đọc file này nếu packet không trỏ một mục.
- Mỗi turn: [`docs/agents/NOW.md`](agents/NOW.md). Archive `docs/agents/archive/` — không mở.

---

## Phạm vi owner

- **Active:** `dev.atz.vn` — `backend/`, `frontend/`, `docker-compose.dev.yml`
- **Không** phát triển prod Streamlit / cutover prod trừ khi owner mở lại (ADR 0009)
- **Một bảng iBoard** — lọc ngày = subset trên cùng `#board-table` (không tab bảng riêng)

---

## Đã ship (gần nhất)

| Commit | Nội dung |
|--------|----------|
| **`acf4361`** | **Advisor 0–100** (P1–P3 spec FILTER_SCORING_HUONG1): `engine/advisor_score.py`, `config/advisor_score.yaml`, filter `advisor`, Streamlit chế độ 「Cố vấn」, debug overlay `FILTER-ADVISOR`, filter-runner `plan_flow_kinds` + foreign flow |
| **`acf4361`** | **iBoard Tín hiệu ngày + Cố vấn:** `POST /api/iboard/daily-signals` — filter `rsi\|macd\|ma\|advisor`, body `buy_min_total` (advisor); UI toolbar **Quét** + **Điểm ≥** |
| `8e39d90` | iBoard daily signals (F1 subset) trên cùng bảng |
| `6228f95`… | Danh mục Phases A–D (portfolio API, Authentik, F3, …) |

**Spec:** `docs/specs/FILTER_SCORING_HUONG1.md` — P1–P3 xong; P4+ (đa TF, smart money) ngoài scope.

**API Danh mục (giữ):** `GET/PUT /api/portfolio/positions`, `POST .../migrate`, `GET /api/account/me`, quotes, F3 alerts, sectors/f3.

---

## iBoard — cách dùng (đã verify dev.atz.vn)

1. **Live WS** — lọc tick (FilterEngine), bảng đầy mã theo tab sàn.
2. **Tín hiệu ngày** — **ẩn hết mã** cho đến khi bấm **Quét** (`dailySignalSet === null` → `rowVisible` false). UX hiện tại, không phải lỗi deploy.
3. Sau **Quét:** subset mã khớp OHLCV filter; status: `Tín hiệu ngày · {filter} · {matched}/{scanned} hit · N mã`.
4. **Cố vấn:** filter **Cố vấn (0–100)** + **Điểm ≥** (mặc định 65; thử 40–50 nếu ít hit) + **Quét**.

**API:**

- `GET /api/iboard/daily-signals/filters`
- `POST /api/iboard/daily-signals` `{ "market": "HOSE|VN30|...", "filter": "rsi|macd|ma|advisor", "buy_min_total": 65? }`  
  → `symbols[]`, `hits[]` (advisor có `total`, `trend`, `flow`, `short_term`).

**Dữ liệu:** quét đọc `data/ohlcv/{SYMBOL}.csv` (mount VPS). `scanned=0` → thiếu/cũ OHLCV.

**Owner chốt (lọc):** không tab 「Bộ lọc tín hiệu」riêng trên SPA; Streamlit vẫn có Bộ lọc + chế độ Cố vấn (legacy UI, khác stack priceboard).

---

## Ops dev VPS (bắt buộc đọc)

| Mục | Chi tiết |
|-----|----------|
| **Branch** | `scripts/deploy-vps.env` → **`ATZ_VPS_BRANCH=main`**. Deploy nhánh feature (vd. `feature/priceboard-debug-trace`) → dev thiếu advisor/daily API. |
| **Rebuild** | Sau đổi `Dockerfile.dev` / `atz_pkg/engine` → `docker compose -f docker-compose.dev.yml build api` (+ recreate). Bind mount `backend/` + `frontend/`; engine advisor **trong image**. |
| **Kiểm tra nhanh** | VPS: `curl http://127.0.0.1:8000/api/iboard/daily-signals/filters` → có `"advisor"`. |
| Worker | `PRICEBOARD_SOURCE=ssi\|mock`; watchlist ≈ `board_universe` |
| Mount | `data/ohlcv`, `data/portfolio.db`, `config/debug_overlay.yaml` |
| Filter runner | Filter `advisor` qua user config SQLite — xem `docs/troubleshooting.md` mục Filter Runner |

---

## Việc tiếp (gợi ý)

1. ~~UX Tín hiệu ngày~~ — full rổ + banner trước Quét (local).
2. ~~Daily signals mở rộng~~ — filter `candle|volume|foreign` + cache theo ngày VN (`clear_daily_scan_cache`).
3. ~~Top 20 KL phiên~~ — nguồn **Top 20 KL phiên** trên toolbar (WS snapshot).
4. ~~Cột CV cố vấn~~ — sau Quét filter advisor + tooltip breakdown.
5. **Parity / cutover** — ADR 0007 checklist (prod ngoài scope mặc định).
6. **CapitalLedger / NAV** — optional Danh mục.

---

## Prompt gợi ý chat mới

```text
Pull. Đọc docs/agents/NOW.md. Nếu Doing là việc của mình, mở đúng docs/agents/tasks/<ID>.md. Không mở archive. Xong thì cập nhật NOW (5 dòng Last executor) rồi dừng.
```

---

## Test local (trước merge/push/deploy)

```bash
./scripts/check-dev.sh              # pytest smoke + docker healthz + API filters
./scripts/check-dev.sh --pytest-only # nhanh, không docker
```
