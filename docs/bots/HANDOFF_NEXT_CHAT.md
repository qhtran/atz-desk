# Handoff — chat tiếp theo (priceboard FastAPI / iBoard)

**Ngày:** 2026-10-21 (SPA 4 tab + Screener trên VPS)  
**Branch:** `feature/realtime-fastapi`  
**HEAD (đã push):** `a01ea91`  
**Orchestrator:** Cursor · Bot code paused · **cấm** sửa nginx `stream.d` / sshd / UFW trừ `user_confirmed_infra: yes`.

**Trigger chat mới:** user chỉ cần gõ **`call progress`** (hoặc `progress`) → agent đọc file này + làm mục **Next** bên dưới, không hỏi lại context dài.

Đọc trước: `AGENTS.md`, `docs/architecture.md` §8.1, file này, `docs/specs/PRICEBOARD_P1_DEPTH_NN.md`.

---

## Khi user nói `call progress` — làm ngay

1. `git checkout feature/realtime-fastapi && git pull` (local).  
2. Tóm tắt 5 dòng: HEAD · VPS stack · P0 còn gì · P1 · Screener.  
3. **Ưu tiên theo giờ ICT:**
   - **Trong phiên GD (≈09:00–15:00):** verify tick live `dev.atz.vn` + capture SSI schema → điền P1 plan §4 → hỏi xác nhận rồi code partial parse.  
   - **Ngoài phiên:** không giả tick live; có thể harden screener/tests/docs; chuẩn bị checklist giờ mở cửa.  
4. **Không** đụng `stream.d` / sshd / UFW / `atz-redis` prod.  
5. FE volume-mount: `git pull` VPS đủ cho HTML; API Python đổi → `docker compose -f docker-compose.dev.yml restart api` (không `--remove-orphans`).

---

## Đã xong (snapshot)

| Hạng mục | Chi tiết |
|----------|----------|
| Stack | `docker-compose.dev.yml` · **`name: atz_priceboard`** · Redis `:6380` · API `:8000` · join `vnstocks_default` |
| FE SPA | `frontend/index.html` — 4 tab: **Giao dịch iBoard** · **Bộ lọc tín hiệu** · **Danh mục** · **Tin tức/Nghiên cứu** · bảng `.atz-table` · 1 WS fan-out · **không** link site cũ |
| Screener | `backend/screener.py` `FilterEngine` · `POST /api/screener` · `GET /api/screener/presets` · FE toolbar compose (KL/%/flags AND/OR) · tests `tests/test_screener.py` Pass |
| BE | FastAPI `/` + `/ws/priceboard` · Redis `priceboard_ticks` + `priceboard:quotes` |
| Volume gate | `min_volume: 500000` |
| Worker | VPS **`PRICEBOARD_SOURCE=ssi`** · channels DATA+X-Quote+X-Trade+MI |
| Public | `https://dev.atz.vn` — Authentik ForwardAuth · TLS OK |
| P0 browser (~02:30 ICT) | Login/WS/index/tabs/search **Pass** · tick live **BLOCKED** ngoài phiên |
| P1 plan | [`docs/specs/PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md) — **chưa** code map depth |
| Rollback FE/API (local) | `.rollback/screener-20261021-0300/` (gitignored) |
| Local OrbStack priceboard | **đã stop** (tránh chiếm `:8000`) |

**Không ghi** `idx:quote:*` (tránh dual-writer với `atz-ssi-stream`).

---

## VPS

| Mục | Giá trị |
|-----|---------|
| Path | `/opt/vnstocks` · branch `feature/realtime-fastapi` @ tip |
| Compose | `atz_priceboard` · api + redis-dev + ssi-worker |
| Mount | `./frontend` + `./backend` → `/app/...` |
| Prod | Streamlit + `atz-redis` **song song** |

```bash
cd /opt/vnstocks && git pull --ff-only origin feature/realtime-fastapi
# chỉ khi đổi Python API:
docker compose -f docker-compose.dev.yml restart api
# log SSI:
docker compose -f docker-compose.dev.yml logs -f --tail=100 ssi-worker
```

---

## Next (ưu tiên)

### P0 — giờ mở cửa
1. Browser `dev.atz.vn`: tick `source=SSI_WS` · volume gate · flash.  
2. Worker log: LIVE-CONNECT / ticks (che token).

### P1 — depth / NN
1. Capture X-Quote/X-Trade/MI → bảng map trong plan.  
2. Partial parse (không bắt buộc `last`) · tắt/gate `enrichDepth` fake.  
3. `tests/test_tick_contract.py`.

### P2
- PR → `main` khi P0 tick Pass · throttle WS · quan hệ `atz-ssi-stream`.

---

## Câu mở chat mới (copy — hoặc chỉ gõ `call progress`)

```
call progress

@docs/bots/HANDOFF_NEXT_CHAT.md
feature/realtime-fastapi @ a01ea91 · https://dev.atz.vn
Không đụng stream.d / sshd / UFW / atz-redis prod.
```
