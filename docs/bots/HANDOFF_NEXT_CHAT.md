# Handoff — chat tiếp theo (priceboard FastAPI / iBoard)

**Ngày:** 2026-10-21 (P0 browser Pass ngoài phiên · tick BLOCKED)  
**Branch:** `feature/realtime-fastapi`  
**HEAD (đã push):** `3c0e7f4`  
**Orchestrator:** Cursor · Bot code paused · **cấm** sửa nginx `stream.d` / sshd / UFW trừ `user_confirmed_infra: yes`.

Đọc trước: `AGENTS.md`, `docs/architecture.md` §8.1, `docs/infrastructure/VPS_NETWORK.md`, `docs/adr/0008-ssi-websocket-primary.md`, `config/priceboard.yaml`, `docs/specs/PRICEBOARD_P1_DEPTH_NN.md`, file này.

---

## Đã xong trên branch này

| Hạng mục | Chi tiết |
|----------|----------|
| Stack | `docker-compose.dev.yml` + `Dockerfile.dev` · **`name: atz_priceboard`** (tách Redis prod) · Redis `:6380` · API `:8000` · API cũng join **`vnstocks_default`** (nginx DNS) |
| FE | `frontend/index.html` — YSVN/SSI: header (brand + Stock Rating/Tín hiệu → atz.vn · search · settings) · Index Cards (điểm + sparkline + KL/GT + Tăng/Giảm/TC/Trần/Sàn) · Market tabs **HOSE / VN30 / HNX / UPCOM** · live search · sticky pin ★ · WS reconnect |
| BE | FastAPI `/` → `index.html` · `/ws/priceboard` · Redis `priceboard_ticks` + Hash `priceboard:quotes` |
| Volume gate | `backend/volume_filter.py` · `min_volume: 500000` · index luôn giữ · equity `vol==0` hiện · `0<vol<500K` → `hdel` + `{type:remove}` |
| Worker | `PRICEBOARD_SOURCE=mock\|ssi` · **VPS đang `ssi`** · `ssi_live.py` → `wss://stream.ssi.com.vn/ws/v3` |
| Public | **`https://dev.atz.vn`** — TLS LE · Authentik ForwardAuth · `/healthz` + `/outpost…` bypass · `/` + `/ws/` auth |
| Nginx path | Volume `n8n_nginx_config` → `conf.d/dev.atz.vn.conf` (repo: `deploy/nginx_dev.conf`) · listen **8443 ssl proxy_protocol** · **không** sửa `stream.d` |
| Cert renew | Host hook `/etc/letsencrypt/renewal-hooks/deploy/sync-nginx-volume-certs.sh` copy sang volume LE Docker |
| Authentik | Proxy Provider `atz.vn` mode **`forward_domain`**, cookie `atz.vn` (subdomain dùng chung) |
| Secret | Chỉ `SSI_CONSUMER_*` từ `.env` — **không** paste chat / không commit |
| P1 plan | [`docs/specs/PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md) — draft map depth/NN, **chưa** code |

**Không ghi** `idx:quote:*` (tránh dual-writer với `atz-ssi-stream`).

---

## VPS hiện tại (verify 2026-10-21)

| Mục | Giá trị |
|-----|---------|
| Path / branch | `/opt/vnstocks` · `feature/realtime-fastapi` (kéo tới HEAD mới khi deploy docs) |
| Compose project | `atz_priceboard` |
| Containers | `atz-priceboard-api-dev` · `atz-redis-dev` · `atz-ssi-worker-dev` (healthy) |
| Source | `PRICEBOARD_SOURCE=ssi` |
| Public health | `GET https://dev.atz.vn/healthz` → **200** |
| Public auth | Authentik ForwardAuth · login browser **Pass** (2026-10-21 ~02:30 ICT) |
| Local OrbStack | **đã stop** (tránh chiếm `:8000`) — không còn tunnel local |
| Prod | `atz-redis` + Streamlit stack **song song**, không đụng |

```bash
# Soi public (sau login Authentik)
open https://dev.atz.vn

# Tunnel dự phòng (khi local không bind 8000)
ssh -L 8000:127.0.0.1:8000 root@112.213.88.230
```

---

## Lệnh hay dùng

```bash
git checkout feature/realtime-fastapi && git pull

# Local OrbStack
export PATH="/Applications/OrbStack.app/Contents/MacOS/xbin:$PATH"
docker compose -f docker-compose.dev.yml up --build -d

# VPS — chỉ HTML / docs
cd /opt/vnstocks && git pull --ff-only

# VPS — rebuild worker/api (giữ project name trong compose)
cd /opt/vnstocks
PRICEBOARD_SOURCE=ssi docker compose -f docker-compose.dev.yml up -d --build

# Log SSI
docker compose -f docker-compose.dev.yml logs -f ssi-worker
# kỳ vọng: WORKER-BOOT source=ssi · LIVE-SEED min_volume=500000 · LIVE-CONNECT · LIVE-SUBSCRIBED
```

**Cấm:** `docker compose … --remove-orphans` trên file.dev · chạy compose.dev **thiếu** `name: atz_priceboard` (đã từng thay nhầm `atz-redis` prod).

---

## Việc chat sau (ưu tiên)

### P0 — Browser + giờ giao dịch

#### Kết quả verify 2026-10-21 ~02:30 ICT (`https://dev.atz.vn`)

| Case | Kết quả |
|------|---------|
| Login Authentik → board load | **Pass** |
| WS `wss://dev.atz.vn/ws/priceboard` · UI `connected` · VPS `WS-CONNECT` · `healthz clients≥1` | **Pass** |
| Index cards (VNINDEX/VN30/HNX/UPCOM seed `SSI_WS`) | **Pass** |
| Tab VN30 | **Pass** |
| Search mã (vd SSI) | **Pass** |
| Tick live `source=SSI_WS` · volume gate · depth thật | **BLOCKED** — ngoài phiên (~02:30); Redis equity `last=0`; FE `enrichDepth` fake |

**Đã xác nhận sớm (curl ~02:12):** healthz 200 · `/` 302 Authentik.  
**Ops:** phiên theo dõi `docker logs -f` VPS **đã dừng** — bật lại lúc giờ mở cửa.

#### Còn lại (giờ mở cửa)

1. Tick `source=SSI_WS` đổi giá/KL · volume gate `min_volume=500000`.  
2. Capture schema X-Quote/X-Trade/MI → điền [`PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md) §4.  
3. Nếu kẹt callback chỉ về `atz.vn`: cân nhắc Proxy Provider riêng `dev.atz.vn` (hiện `forward_domain` đã Pass browser).

### P1 — Data chất lượng (plan sẵn)

Chi tiết: [`docs/specs/PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md).

1. Capture schema giờ mở cửa → điền bảng map.  
2. Partial parse (không bắt buộc `last`) + alias → `bid*`/`ask*`/`foreign*`.  
3. Index card GT (Tỷ): `tradeValue` khi schema rõ.  
4. Tắt/gate `enrichDepth` fake; test `tests/test_tick_contract.py`.

### P2 — Merge / hệ sinh thái

- Song song vs gộp `atz-ssi-stream` (chỉ `priceboard:*`).  
- Throttle fan-out nếu >100 client.  
- PR: `feature/realtime-fastapi` → `main` khi P0 tick giờ mở cửa Pass.

---

## Lệnh tắt / giữ

- **Giữ** stack priceboard trên VPS.  
- Dừng chỉ priceboard: `cd /opt/vnstocks && docker compose -f docker-compose.dev.yml down`  
  (không `down` compose prod).

---

## Câu mở chat mới (copy)

> Tiếp `feature/realtime-fastapi` @ tip + `docs/bots/HANDOFF_NEXT_CHAT.md` + `docs/specs/PRICEBOARD_P1_DEPTH_NN.md`.  
> Public: `https://dev.atz.vn` — P0 Pass (login/WS/index/tabs/search); tick **BLOCKED** ngoài phiên. Stack VPS `atz_priceboard` SSI, `min_volume=500000`. Local OrbStack priceboard đã stop.  
> Việc tiếp: P0 tick giờ mở cửa + P1 capture depth/NN rồi code.  
> **Không** đụng `stream.d` / sshd / UFW / `atz-redis` prod.
