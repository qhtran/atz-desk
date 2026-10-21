# Handoff — chat tiếp theo (priceboard FastAPI / iBoard)

**Ngày:** 2026-10-21 (~07:36 ICT)  
**Branch:** `feature/realtime-fastapi`  
**HEAD (đã push + VPS pull):** `adc552d`  
**Orchestrator:** Cursor · Bot code paused · **cấm** sửa nginx `stream.d` / sshd / UFW trừ `user_confirmed_infra: yes`.

**Trigger chat mới:** user gõ **`call progress`** → đọc file này + làm mục **Next**, không hỏi lại context dài.

Đọc trước: `AGENTS.md`, `docs/architecture.md` §8.1, file này, `docs/specs/PRICEBOARD_P1_DEPTH_NN.md`.

---

## Khi user nói `call progress` — làm ngay

1. `git checkout feature/realtime-fastapi && git pull` (local / cloud worktree).  
2. Tóm tắt 5 dòng: HEAD · VPS stack · P0 còn gì · P1 · Screener / spark.  
3. **Ưu tiên theo giờ ICT:**
   - **Trong phiên GD (≈09:00–15:00):** verify tick live `dev.atz.vn` + capture SSI schema → điền P1 plan §4 → hỏi xác nhận rồi code partial parse.  
   - **Ngoài phiên:** không giả tick live; harden screener/tests/docs OK.  
4. **Không** đụng `stream.d` / sshd / UFW / `atz-redis` prod.  
5. Deploy FE: SSH VPS `git pull` (volume-mount HTML). API Python đổi → `docker compose -f docker-compose.dev.yml restart api` (không `--remove-orphans`).

---

## SSH VPS (bắt buộc nhớ — key đã sẵn)

```bash
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && git pull --ff-only origin feature/realtime-fastapi'
```

- Host: `root@112.213.88.230` · path `/opt/vnstocks` · **đừng** tìm skill SSH — gọi thẳng.  
- Public: `https://dev.atz.vn` (Authentik ForwardAuth).

---

## Đã xong (snapshot)

| Hạng mục | Chi tiết |
|----------|----------|
| Stack | `docker-compose.dev.yml` · **`name: atz_priceboard`** · Redis `:6380` · API `:8000` · join `vnstocks_default` |
| FE SPA | `frontend/index.html` — 4 tab iBoard / Screener / Danh mục / Tin tức · `.atz-table` · 1 WS |
| Spark index (1a) | **Done @ `adc552d`** — `renderSparkSvg` / `patchSparkSvg`: gradient area + marker + dashed **ref/high/low** · patch attrs (không re-innerHTML card) · VPS đã pull |
| Screener | `backend/screener.py` + `POST /api/screener` + FE toolbar · `tests/test_screener.py` Pass |
| BE | FastAPI `/` + `/ws/priceboard` · Redis `priceboard_ticks` + `priceboard:quotes` |
| Volume gate | `min_volume: 500000` |
| Worker | VPS `PRICEBOARD_SOURCE=ssi` · DATA+X-Quote+X-Trade+MI |
| P0 browser | Login/WS/tabs **Pass** · tick live verify **còn** lúc mở cửa |
| P1 plan | [`docs/specs/PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md) — **chưa** code map depth |
| Local OrbStack priceboard | **stop** (tránh chiếm `:8000`) |

**Không ghi** `idx:quote:*` (tránh dual-writer với `atz-ssi-stream`).

---

## VPS

| Mục | Giá trị |
|-----|---------|
| Path | `/opt/vnstocks` · `feature/realtime-fastapi` @ `adc552d` |
| Compose | `atz_priceboard` · api + redis-dev + ssi-worker |
| Mount | `./frontend` + `./backend` → `/app/...` |
| Prod | Streamlit + `atz-redis` **song song** |

```bash
# FE only:
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && git pull --ff-only origin feature/realtime-fastapi'
# API Python:
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && docker compose -f docker-compose.dev.yml restart api'
# SSI log (che token):
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && docker compose -f docker-compose.dev.yml logs -f --tail=100 ssi-worker'
```

---

## Next (ưu tiên)

### P0 — giờ mở cửa (~09:00 ICT)
1. Browser `dev.atz.vn`: tick `source=SSI_WS` · volume gate · flash · **spark area/marker/dashed** trên index cards.  
2. Worker log: LIVE-CONNECT / ticks (che token).

### P1 — depth / NN
1. Capture X-Quote/X-Trade/MI → bảng map trong plan §4.  
2. Partial parse (không bắt buộc `last`) · tắt/gate `enrichDepth` fake.  
3. `tests/test_tick_contract.py`.

### P2 / backlog spark
- Cột spark trên hàng cổ phiếu (đã từ chối 1b — chỉ làm khi user chọn lại).  
- Field `open` trong tick_contract nếu SSI có.  
- PR → `main` khi P0 tick Pass · throttle WS · quan hệ `atz-ssi-stream`.

---

## Câu mở chat / Cloud Agent

```
call progress

@docs/bots/HANDOFF_NEXT_CHAT.md
feature/realtime-fastapi @ adc552d · https://dev.atz.vn
SSH: root@112.213.88.230 → /opt/vnstocks
Không đụng stream.d / sshd / UFW / atz-redis prod.
```
