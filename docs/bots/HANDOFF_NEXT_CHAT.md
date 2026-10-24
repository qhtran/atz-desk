# Handoff — chat tiếp theo (priceboard FastAPI / iBoard)

**Ngày:** 2026-10-25 (~01:50 ICT)  
**Branch (active dev):** `feature/priceboard-debug-trace`  
**HEAD (đã push + VPS pull):** `122b243`  
**Base merge target:** `feature/realtime-fastapi` (chưa merge debug trace)  
**Orchestrator:** Cursor · Bot code paused · **cấm** sửa nginx `stream.d` / sshd / UFW trừ `user_confirmed_infra: yes`.

**Trigger chat mới:** user gõ **`call progress`** hoặc **`HANDOFF_NEXT_CHAT`** → đọc file này + làm mục **Next**, không hỏi lại context dài.

Đọc trước: `AGENTS.md`, `docs/architecture.md` §8.1, file này, `docs/specs/PRICEBOARD_DEBUG.md`, `docs/specs/PRICEBOARD_P1_DEPTH_NN.md`.

**Phạm vi dev.atz.vn:** `backend/`, `frontend/`, `docker-compose.dev.yml` — **không** refactor Streamlit `src/atz` trừ khi user yêu cầu.

---

## Khi user nói `call progress` — làm ngay

1. `git checkout feature/priceboard-debug-trace && git pull` (local / cloud worktree).  
2. Tóm tắt 5 dòng: HEAD · VPS stack · P0 còn gì · P1 · Screener / spark / debug.  
3. **Ưu tiên theo giờ ICT:**
   - **Trong phiên GD (≈09:00–15:00):** verify tick live `dev.atz.vn` + capture SSI schema → điền P1 plan §4 → hỏi xác nhận rồi code partial parse.  
   - **Ngoài phiên:** không giả tick live; harden screener/tests/docs OK.  
4. **Không** đụng `stream.d` / sshd / UFW / `atz-redis` prod.  
5. Deploy dev: SSH VPS `git pull` (volume-mount `backend/` + `frontend/`). Python đổi → `docker compose -f docker-compose.dev.yml restart api ssi-worker` (không `--remove-orphans`).

---

## SSH VPS (bắt buộc nhớ — key đã sẵn)

```bash
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && git pull --ff-only origin feature/priceboard-debug-trace'
```

- Host: `root@112.213.88.230` · path `/opt/vnstocks` · **đừng** tìm skill SSH — gọi thẳng.  
- Public: `https://dev.atz.vn` (Authentik ForwardAuth).

---

## Đã xong (snapshot)

| Hạng mục | Chi tiết |
|----------|----------|
| Stack | `docker-compose.dev.yml` · **`name: atz_priceboard`** · Redis `:6380` · API `:8000` · join `vnstocks_default` |
| **Debug trace @ `5cc26b9`** | `backend/observability/` · log `[DBG-…-PB-*]` · **`ERR-PB-001…009`** · JSON `origin` (file/line/function) · spec [`PRICEBOARD_DEBUG.md`](../specs/PRICEBOARD_DEBUG.md) · `tests/test_priceboard_observability.py` Pass |
| FE SPA | `frontend/index.html` — 4 tab iBoard / Screener / Danh mục / Tin tức · `.atz-table` · 1 WS |
| Spark index (1a) | **Done** — `renderSparkSvg` / `patchSparkSvg`: gradient area + marker + dashed **ref/high/low** |
| Screener | `POST /api/screener` · rule invalid → **400 + ERR-PB-008** · `tests/test_screener.py` Pass |
| BE | FastAPI `/` + `/ws/priceboard` · Redis `priceboard_ticks` + `priceboard:quotes` |
| Volume gate | `min_volume: 500000` |
| Worker | VPS `PRICEBOARD_SOURCE=ssi` · DATA+X-Quote+X-Trade+MI · log `PB-SSI-LIVE-*` |
| VPS deploy | **2026-10-25** pull `dea3b27` (handoff) · api healthy · `/healthz` 200 |
| PR | #4 → `feature/realtime-fastapi` (debug trace + handoff) |
| P0 browser | Login/WS/tabs **Pass** · tick live runbook [P0_LIVE_VERIFY.md](P0_LIVE_VERIFY.md) · capture §4 **phiên mở** |
| P1 prep | FE gate `enrichDepth` · partial parse tests · `ERR-PB-006` rate-limit worker |
| P1 plan | [`PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md) — **chưa** code map depth |
| Local OrbStack priceboard | **stop** (tránh chiếm `:8000`) |
| Backlog doc (local) | `docs/specs/FILTER_SCORING_HUONG1.md` — **untracked**, Streamlit/filter scoring, **ngoài** scope priceboard trừ khi user chọn |

**Không ghi** `idx:quote:*` (tránh dual-writer với `atz-ssi-stream`).

---

## VPS

| Mục | Giá trị |
|-----|---------|
| Path | `/opt/vnstocks` · **`feature/priceboard-debug-trace`** @ **`5cc26b9`** |
| Compose | `atz_priceboard` · api + redis-dev + ssi-worker |
| Mount | `./frontend` + `./backend` → `/app/...` |
| Prod | Streamlit + `atz-redis` **song song** |

```bash
# Code (FE + backend mount):
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && git pull --ff-only origin feature/priceboard-debug-trace'
# API + worker Python:
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && docker compose -f docker-compose.dev.yml restart api ssi-worker'
# Log debug (grep mã lỗi):
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && docker compose -f docker-compose.dev.yml logs --tail=200 api ssi-worker 2>&1 | grep -E "ERR-PB|PB-"'
# SSI log (che token):
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && docker compose -f docker-compose.dev.yml logs -f --tail=100 ssi-worker'
```

---

## Next (ưu tiên)

### P0 — giờ mở cửa (~09:00 ICT)
1. Browser `dev.atz.vn`: tick `source=SSI_WS` · volume gate · flash · spark index cards.  
2. Worker log: `PB-SSI-LIVE-CONNECT` / ticks (che token).  
3. (Tuỳ chọn) Gây lỗi Redis tạm → xác nhận log có `ERR-PB-001` + `origin`.

### P0.5 — git
1. PR `feature/priceboard-debug-trace` → `feature/realtime-fastapi` (hoặc `main` theo quy ước team).  
2. Sau merge: đổi VPS branch hoặc pull nhánh target.

### P1 — depth / NN
1. Capture X-Quote/X-Trade/MI → bảng map trong plan §4.  
2. Partial parse (không bắt buộc `last`) · tắt/gate `enrichDepth` fake.  
3. `tests/test_tick_contract.py` · gán **ERR-PB-006** khi parse fail có ý nghĩa.

### P2 / backlog
- Cột spark trên hàng cổ phiếu (chỉ khi user chọn lại).  
- Field `open` trong tick_contract nếu SSI có.  
- Filter scoring Hướng 1 (`FILTER_SCORING_HUONG1.md`) — **priceboard/screener**, không Streamlit legacy.

---

## Câu mở chat / Cloud Agent

```
call progress

@docs/bots/HANDOFF_NEXT_CHAT.md
feature/priceboard-debug-trace @ 5cc26b9 · https://dev.atz.vn
SSH: root@112.213.88.230 → /opt/vnstocks
Debug: docs/specs/PRICEBOARD_DEBUG.md (ERR-PB-*)
Không đụng stream.d / sshd / UFW / atz-redis prod.
```
