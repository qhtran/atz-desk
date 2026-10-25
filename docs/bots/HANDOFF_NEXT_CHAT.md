# Handoff — chat tiếp theo (DEV · Trạm Trading)

**Ngày:** 2026-10-25 (~22:06 ICT)  
**Branch làm việc:** `cursor/demo-trading-station-ui-15d3` (demo UI) · base `feature/realtime-fastapi`  
**Orchestrator:** Cursor · **phạm vi chỉ DEV** (`dev.atz.vn`) — xem `.cursor/rules/dev-atz-scope.mdc`  
**Cấm:** nginx `stream.d` / sshd / UFW / `atz-redis` prod trừ `user_confirmed_infra: yes`

**Trigger:** user gõ **`call progress`** → đọc file này + `docs/specs/DEV_TRADING_STATION_PLAN.md` → làm **Next** (P1), không hỏi lại context dài.

---

## Khi user nói `call progress`

1. `git fetch && git checkout feature/realtime-fastapi && git pull` (hoặc branch PR đang mở).  
2. Tóm tắt 5 dòng: HEAD · demo UI · plan Trạm · P1 còn gì · VPS.  
3. **Next mặc định:** **P1** — `backend/core/` (database + logging_middleware + errors) + tests; hỏi xác nhận 1 dòng nếu lệch plan.  
4. Không đụng prod/`src/`.  
5. Deploy FE: SSH VPS `git pull` (volume-mount HTML). API Python đổi → `docker compose -f docker-compose.dev.yml restart api`.

---

## Đã xong (snapshot)

| Hạng mục | Chi tiết |
|----------|----------|
| Index parse SSI | Merged `feature/realtime-fastapi` @ `8b8b343` — `v`/`c`, volume, book |
| UI demo đích | `frontend/demo-final.html` **đã duyệt** · PR [#5](https://github.com/qhtran/quanlychungkhoan/pull/5) |
| Plan Trạm Trading | `docs/specs/DEV_TRADING_STATION_PLAN.md` — chốt avg/fee/tax/modules |
| Stack DEV | `docker-compose.dev.yml` · `atz_priceboard` · Redis `:6380` · API `:8000` |
| Public | `https://dev.atz.vn` (Authentik ForwardAuth) |

---

## Next (ưu tiên)

### P1 — core + trace (làm trước)
1. `backend/core/database.py`, `logging_middleware.py`, `errors.py`, `redis_client.py`  
2. Mount middleware vào `backend/main.py`  
3. `tests/test_logging_middleware.py` Pass  
4. `/healthz` vẫn 200  

### P2 → P5
Xem bảng trong `docs/specs/DEV_TRADING_STATION_PLAN.md` (trading module → API → FE → assets).

### VPS / SSH
```bash
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && git pull --ff-only origin feature/realtime-fastapi'
# Demo UI (khi branch/PR đã merge hoặc checkout PR branch):
# https://dev.atz.vn/demo-final.html
```
Cloud Agent có thể cần SSH-over-443 `rd.atz.vn` + key (không commit key).

---

## Câu mở chat / Cloud Agent

```
call progress

@docs/bots/HANDOFF_NEXT_CHAT.md
@docs/specs/DEV_TRADING_STATION_PLAN.md
DEV only · P1 core middleware + DB skeleton
Không đụng stream.d / sshd / UFW / atz-redis prod / src/
```
