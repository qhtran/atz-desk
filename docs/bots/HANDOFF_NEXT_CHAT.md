# Handoff — chat tiếp theo (priceboard FastAPI)

**Ngày:** 2026-10-21  
**Branch:** `feature/realtime-fastapi` (đã push scaffold + iBoard UI + hybrid worker)  
**Orchestrator:** Cursor · Bot code paused · **cấm** sửa nginx stream/sshd/UFW trừ confirm infra.

Đọc trước: `AGENTS.md`, `docs/adr/0008-ssi-websocket-primary.md`, `config/priceboard.yaml`, file này.

---

## Đã xong trên branch này

| Hạng mục | Chi tiết |
|----------|----------|
| Stack dev | `docker-compose.dev.yml` + `Dockerfile.dev` · Redis `:6380` · API `:8000` · OrbStack OK |
| FE | `frontend/index.html` — iBoard dark, sticky ★/Mã CK (`border-separate`), pin + sticky dọc, flash tick, WS reconnect |
| BE | FastAPI `/ws/priceboard` + Redis Pub/Sub `priceboard_ticks` + Hash `priceboard:quotes` |
| Worker hybrid | `backend/ssi_worker.py` · `PRICEBOARD_SOURCE=mock\|ssi` (default **mock**) |
| Live SSI | `backend/ssi_live.py` — auth REST token → `wss://stream.ssi.com.vn/ws/v3` · channels `DATA,X-Quote,X-Trade,MI` · topics index + `quote/trade.SYM@tick` VN30 |
| Contract | `backend/tick_contract.py` — FE cần `symbol,last,ref,ceil,floor,volume,bid*,ask*,…` |
| Config | `config/priceboard.yaml` · ENV thắng file |
| Secret | Chỉ `SSI_CONSUMER_ID` / `SSI_CONSUMER_SECRET` từ host `.env` — **không** paste chat / không commit |

**Không ghi** `idx:quote:*` (tránh dual-writer với `atz-ssi-stream`).

---

## HEAD / verify local

```bash
git checkout feature/realtime-fastapi && git pull
export PATH="/Applications/OrbStack.app/Contents/MacOS/xbin:$PATH"
docker compose -f docker-compose.dev.yml up --build -d
# UI: http://127.0.0.1:8000
```

Log mock: `DBG-PRICEBOARD-SSI-MOCK-READY`  
Bật SSI:

```bash
# trong .env đã có SSI_CONSUMER_* rồi:
PRICEBOARD_SOURCE=ssi docker compose -f docker-compose.dev.yml up -d --build ssi-worker
docker compose -f docker-compose.dev.yml logs -f ssi-worker
# kỳ vọng: DBG-PRICEBOARD-WORKER-BOOT source=ssi · LIVE-CONNECT · LIVE-SUBSCRIBED
```

---

## Việc chat sau (ưu tiên)

### P0 — Verify SSI live (giờ giao dịch)

1. Confirm `.env` có `SSI_CONSUMER_*` (không đưa vào chat).  
2. `PRICEBOARD_SOURCE=ssi` · xem tick `source=SSI_WS` trên board.  
3. Nếu X-Quote/X-Trade/MI không đẩy payload: giữ `DATA` + topics `quote.*`/`trade.*` (đã có); tinh chỉnh `parse_ssi_envelope` theo sample log thật (che token).  
4. Depth/NN: map field SSI → `bid*`/`ask*`/`foreign*` khi schema rõ.

### P1 — Tích hợp hệ sinh thái

- Quyết định: worker priceboard **song song** `atz-ssi-stream` (chỉ `priceboard:*`) hay gộp dần.  
- Nginx `dev.atz.vn` từ `deploy/nginx_dev.conf` — **chỉ** khi `user_confirmed_infra: yes`.  
- Auth board (Authentik) trước public.

### P2 — Chất lượng

- Test contract `tests/test_priceboard_tick_contract.py`.  
- Throttle/coalesce fan-out nếu >100 client.  
- PR: `feature/realtime-fastapi` → `main` khi live verify Pass.

---

## Lệnh tắt / giữ

- **Giữ Docker** khi đang soi UI (đừng `down` trừ khi user yêu cầu).  
- Dừng: `docker compose -f docker-compose.dev.yml down`

---

## Câu mở chat mới (copy)

> Tiếp `feature/realtime-fastapi` + `docs/bots/HANDOFF_NEXT_CHAT.md`. Hybrid mock/ssi đã có. Việc tiếp: verify `PRICEBOARD_SOURCE=ssi` với `.env` SSI_* (không paste secret), chỉnh parse X-Quote/X-Trade/MI theo log thật, giữ contract `tick_contract.py`. Không đụng nginx prod.
