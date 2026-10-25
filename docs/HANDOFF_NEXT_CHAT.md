# Handoff — priceboard dev (chat tiếp theo)

**Cập nhật:** 2026-10-25 (sync HEAD)  
**Nhánh deploy VPS:** `main` — commit **`39d7fe7`** (HĐTL tab sàn + daily UX gần nhất)  
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
| **`39d7fe7`** | Tab sàn **VN30F1M** / **VN30F2M** trên market-bar (HĐTL depth board) |
| `c41b2f7` / `d399410` | Index-bar luôn có VN30F1M/F2M; tab **Khối ngoại** |
| **`2e9ee5d`** | **Daily UX:** full rổ + banner trước Quét; filter OHLCV `candle\|volume\|foreign`; **Top 20 KL phiên** (WS); cột CV cố vấn + tooltip |
| **`774158d`** | `./scripts/check-dev.sh` — smoke pytest + docker healthz + API filters |
| **`78711b7`** | Bus agent: `docs/agents/NOW.md` + archive (PROGRESS stub) |
| **`acf4361`** | **Advisor 0–100** + `POST /api/iboard/daily-signals` (`rsi\|macd\|ma\|advisor`, `buy_min_total`) |
| `6228f95`… | Danh mục Phases A–D (portfolio API, Authentik, F3, …) |

**Spec:** `docs/specs/FILTER_SCORING_HUONG1.md` — P1–P3 xong; P4+ (đa TF, smart money) ngoài scope.

**API Danh mục (giữ):** `GET/PUT /api/portfolio/positions`, `POST .../migrate`, `GET /api/account/me`, quotes, F3 alerts, sectors/f3.

---

## iBoard — cách dùng (đã verify dev.atz.vn)

1. **Live WS** — lọc tick (FilterEngine), bảng đầy mã theo tab sàn (kể cả **VN30F1M/F2M**, **Khối ngoại**).
2. **Tín hiệu ngày** — trước **Quét:** full rổ + banner (không còn ẩn hết mã như bản cũ); sau Quét subset OHLCV.
3. Sau **Quét:** status dạng `Tín hiệu ngày · {filter} · {matched}/{scanned} hit · N mã`.
4. **Cố vấn:** filter **Cố vấn (0–100)** + **Điểm ≥** (mặc định 65; thử 40–50 nếu ít hit) + **Quét** (cột CV + tooltip sau Quét).
5. **Top 20 KL phiên** — nguồn toolbar (WS snapshot).

**API:**

- `GET /api/iboard/daily-signals/filters`
- `POST /api/iboard/daily-signals` `{ "market": "HOSE|VN30|...", "filter": "rsi|macd|ma|candle|volume|foreign|advisor", "buy_min_total": 65? }`  
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
| Mount | `data/ohlcv` (**ro** trong container `api`), `data/portfolio.db`, `config/debug_overlay.yaml` |
| **OHLCV seed (EOD)** | **`./scripts/seed-iboard-ohlcv.sh`** (VPS: tự dùng container `vnstocks` + restart `api` dev). Local có vnstock: fallback `python3 -m backend.ohlcv_seed`. Verify: `POST …/daily-signals` → `scanned>0`. Filter `foreign` cần `data/flow`. |
| Filter runner | Filter `advisor` qua user config SQLite — xem `docs/troubleshooting.md` mục Filter Runner |

---

## Việc tiếp (gợi ý)

**Ưu tiên owner (2026-10-25, ngoài giờ / CN):**

| # | Hướng | Vì sao | Pass gợi ý |
|---|--------|--------|------------|
| **A** | **EOD / OHLCV seed** — tool `python -m backend.ohlcv_seed` (host VPS) | `scanned=0` hoặc hit lệch khi `data/ohlcv` cũ/thiếu | Chạy seed + restart `api`; `POST daily-signals` → `scanned>0` |
| **B** | **HĐTL depth UX** (VN30F1M/F2M) | Tab sàn đã ship; depth vẫn **fake** (`enrichDepth`) tới P1 map X-Quote | Spec `docs/specs/PRICEBOARD_P1_DEPTH_NN.md` — partial tick + tắt fake khi WS có `bid1`; **capture schema cần giờ mở cửa** |

Khác:

1. ~~UX Tín hiệu ngày / filter mở rộng / Top 20 / cột CV~~ — ship `2e9ee5d`.
2. **Parity / cutover** — ADR 0007 (prod ngoài scope mặc định).
3. **CapitalLedger / NAV** — optional Danh mục.

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
