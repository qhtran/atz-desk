# Handoff — chat tiếp theo (priceboard FastAPI / iBoard)

**Ngày:** 2026-10-21 (cập nhật sau UI YSVN + deploy VPS SSI)  
**Branch:** `feature/realtime-fastapi`  
**HEAD (đã push):** `06c43a2` — YSVN header / index cards / market tabs / search  
**Orchestrator:** Cursor · Bot code paused · **cấm** sửa nginx stream/sshd/UFW trừ `user_confirmed_infra: yes`.

Đọc trước: `AGENTS.md`, `docs/architecture.md` §8.1, `docs/adr/0008-ssi-websocket-primary.md`, `config/priceboard.yaml`, file này.

---

## Đã xong trên branch này

| Hạng mục | Chi tiết |
|----------|----------|
| Stack | `docker-compose.dev.yml` + `Dockerfile.dev` · **`name: atz_priceboard`** (tách project — **không** đụng `atz-redis` prod) · Redis `:6380` · API `:8000` |
| FE | `frontend/index.html` — style YSVN/SSI: header (brand + Stock Rating/Tín hiệu → atz.vn · search kính lúp · settings) · Index Cards (điểm + sparkline + KL/GT + Tăng/Giảm/TC/Trần/Sàn) · Market tabs **HOSE / VN30 / HNX / UPCOM** · live search · sticky pin ★ · WS reconnect |
| BE | FastAPI `/` → `index.html` · `/ws/priceboard` · Redis Pub/Sub `priceboard_ticks` + Hash `priceboard:quotes` |
| Volume gate | `backend/volume_filter.py` · `min_volume: 500000` · index luôn giữ · equity `vol==0` hiện · `0<vol<500K` → `hdel` + `{type:remove}` · snapshot cũng lọc |
| Worker | `PRICEBOARD_SOURCE=mock\|ssi` · mock mặc định file; **VPS đang `ssi`** |
| Live SSI | `backend/ssi_live.py` — token REST → `wss://stream.ssi.com.vn/ws/v3` · `DATA,X-Quote,X-Trade,MI` · index + VN30 quote/trade |
| Nginx scaffold | `deploy/nginx_dev.conf` — ForwardAuth Authentik (`/healthz` + `/outpost…` public; `/` + `/ws/` auth) — **chưa apply** `/opt/nginx` |
| Secret | Chỉ `SSI_CONSUMER_*` từ host `.env` — **không** paste chat / không commit |

**Không ghi** `idx:quote:*` (tránh dual-writer với `atz-ssi-stream`).

---

## VPS (dev stack — localhost only)

| Mục | Giá trị |
|-----|---------|
| Path | `/opt/vnstocks` · branch `feature/realtime-fastapi` |
| Compose | `docker compose -f docker-compose.dev.yml …` (project `atz_priceboard`) |
| Containers | `atz-priceboard-api-dev` · `atz-redis-dev` · `atz-ssi-worker-dev` |
| Bind | `127.0.0.1:8000` · `127.0.0.1:6380` — **chưa** public `dev.atz.vn` |
| Source | `.env` → `PRICEBOARD_SOURCE=ssi` · `SSI_CONSUMER_*` đã có |
| FE sync | `./frontend` volume-mount → **`git pull` đủ**, không cần rebuild cho HTML |
| Prod | Stack `vnstocks` + `atz-redis` **song song**, healthy |

Soi UI từ Mac:

```bash
ssh -L 8000:127.0.0.1:8000 root@112.213.88.230
# http://127.0.0.1:8000  (hard-refresh)
```

---

## HEAD / verify local

```bash
git checkout feature/realtime-fastapi && git pull
export PATH="/Applications/OrbStack.app/Contents/MacOS/xbin:$PATH"
# BẮT BUỘC có name: atz_priceboard trong compose (tránh đụng redis prod trên VPS)
docker compose -f docker-compose.dev.yml up --build -d
# UI: http://127.0.0.1:8000
```

Log mock: `DBG-PRICEBOARD-SSI-MOCK-READY`  
SSI:

```bash
PRICEBOARD_SOURCE=ssi docker compose -f docker-compose.dev.yml up -d --build ssi-worker
docker compose -f docker-compose.dev.yml logs -f ssi-worker
# kỳ vọng: WORKER-BOOT source=ssi · LIVE-SEED … min_volume=500000 · LIVE-CONNECT · LIVE-SUBSCRIBED
```

VPS recreate (an toàn):

```bash
cd /opt/vnstocks && git pull --ff-only
# chỉ HTML: đủ
# full rebuild worker/api:
PRICEBOARD_SOURCE=ssi docker compose -f docker-compose.dev.yml up -d --build
```

---

## Việc chat sau (ưu tiên)

### P0 — Verify SSI live (giờ giao dịch)

1. Tunnel soi board: tick `source=SSI_WS`, search + market tabs, pin.  
2. Confirm volume gate: mã `0<vol<500K` biến mất (`type=remove`); đầu ngày `vol=0` vẫn hiện.  
3. Depth/NN: map X-Quote/X-Trade/MI → `bid*`/`ask*`/`foreign*` khi có sample log (che token).  
4. Index card GT (Tỷ): enrich `tradeValue` từ SSI khi schema rõ (hiện suy từ board equities).

### P1 — Public `dev.atz.vn`

- Apply `deploy/nginx_dev.conf` + DNS/TLS — **chỉ** khi `user_confirmed_infra: yes`.  
- Authentik outpost allowlist host `dev.atz.vn`.  
- Không đụng stream `rd.atz.vn` / UFW / sshd.

### P2 — Hệ sinh thái / chất lượng

- Song song vs gộp dần với `atz-ssi-stream` (chỉ `priceboard:*`).  
- Test: `tests/test_volume_filter.py` (+ contract tick khi có).  
- Throttle fan-out nếu >100 client.  
- PR: `feature/realtime-fastapi` → `main` khi live verify Pass.

---

## Lệnh tắt / giữ

- **Giữ** stack priceboard trên VPS khi đang soi.  
- Dừng **chỉ** priceboard: `cd /opt/vnstocks && docker compose -f docker-compose.dev.yml down`  
  (không `down` compose prod; không `--remove-orphans` bừa).

---

## Câu mở chat mới (copy)

> Tiếp `feature/realtime-fastapi` @ `06c43a2` + `docs/bots/HANDOFF_NEXT_CHAT.md`. VPS: project `atz_priceboard`, `PRICEBOARD_SOURCE=ssi`, UI YSVN (search/settings, index cards, HOSE/VN30/HNX/UPCOM), `min_volume=500000`. Việc tiếp: verify tick giờ giao dịch + depth map; nginx `dev.atz.vn` chỉ khi `user_confirmed_infra: yes`. Không đụng nginx stream/prod redis.
