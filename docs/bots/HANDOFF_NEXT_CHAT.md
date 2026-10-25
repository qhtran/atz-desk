# Handoff — chat tiếp theo (dev.atz.vn priceboard + debug overlay)

**Ngày:** 2026-10-25 (~02:45 ICT)  
**Branch (active dev):** `feature/priceboard-debug-trace`  
**HEAD (đã push + VPS pull):** `781ec9e`  
**PR:** [#4](https://github.com/qhtran/quanlychungkhoan/pull/4) → `feature/realtime-fastapi` (chưa merge)  
**Orchestrator:** Cursor · **cấm** sửa nginx `stream.d` / sshd / UFW trừ `user_confirmed_infra: yes`.

**Trigger chat mới:** user gõ **`call progress`**, **`HANDOFF_NEXT_CHAT`**, hoặc dán block **Câu mở chat** → đọc file này + làm **Next**, không hỏi lại context dài.

Đọc trước: `AGENTS.md`, `.cursor/rules/dev-atz-scope.mdc`, `docs/specs/PRICEBOARD_DEBUG.md`, `docs/specs/PRICEBOARD_P1_DEPTH_NN.md`, `docs/bots/P0_LIVE_VERIFY.md`.

**Phạm vi mặc định:** **dev.atz.vn** — `backend/`, `frontend/`, `docker-compose.dev.yml`. Prod **atz.vn** chỉ khi user yêu cầu rõ (overlay đã ship @ `781ec9e`).

---

## Khi user nói `call progress` — làm ngay

1. `git checkout feature/priceboard-debug-trace && git pull`  
2. Tóm tắt 5 dòng: HEAD · VPS dev stack · VPS prod `vnstocks` · P0 live · P1 §4.  
3. **ICT:** trong phiên (~09:00–15:00) → verify tick + capture SSI; ngoài phiên → tests/docs/PR.  
4. Deploy **dev:** pull + `restart api ssi-worker` (mount code). Deploy **prod app:** `docker compose build vnstocks && up -d --no-deps vnstocks` (image, không mount `src/`).  
5. **Không** đụng `stream.d` / sshd / UFW / logic `atz-redis` prod ngoài yêu cầu.

---

## SSH VPS

```bash
ssh -o BatchMode=yes root@112.213.88.230 'cd /opt/vnstocks && git pull --ff-only origin feature/priceboard-debug-trace'
```

| Site | URL | Stack |
|------|-----|--------|
| Dev priceboard | https://dev.atz.vn | `docker-compose.dev.yml` · `atz_priceboard` |
| Prod app | https://atz.vn | `docker-compose.yml` · service **`vnstocks`** `:8501` |

---

## Đã xong (snapshot session này)

| Hạng mục | Chi tiết |
|----------|----------|
| **Observability** | `ERR-PB-001…009` · `origin` file/line · [`PRICEBOARD_DEBUG.md`](../specs/PRICEBOARD_DEBUG.md) |
| **P1 prep** | `enrichDepth` gate (`?fake_depth=0`) · partial parse tests · worker `ERR-PB-006` rate-limit |
| **Inspect overlay dev** | `frontend/debug-overlay.js` · `pb-ui:*` · `GET /api/debug-ui/config` · catalog `ui_catalog.json` · ⌘⇧D · storage **`pb-dbg-on`** |
| **Inspect overlay prod** | Cùng JS trong image · `atz-ui:*` · [`src/atz/ui/debug_overlay.py`](../../src/atz/ui/debug_overlay.py) · static `/static/debug-overlay.*` · catalog `ui_catalog_atz.json` · storage **`atz-dbg-on`** · VPS **rebuilt + restarted** `vnstocks` @ `781ec9e` |
| **Priceboard FE/BE** | iBoard 4 tab · WS · screener · spark index · worker SSI |
| **PR #4** | Mở; chưa merge vào `feature/realtime-fastapi` |
| **Runbook** | [P0_LIVE_VERIFY.md](P0_LIVE_VERIFY.md) (tick live + Inspect checklist) |

**Chưa có (user đã hỏi):** overlay **không** tự hiện file:dòng khi lỗi runtime; backend log `origin` chỉ trên Docker logs; FE errors chưa gắn panel.

**Local uncommitted / untracked:** `.cursor/rules/dev-atz-scope.mdc`, sửa `AGENTS.md` / `atz.mdc`, `docs/specs/FILTER_SCORING_HUONG1.md` — commit khi user bảo.

**Không ghi** `idx:quote:*` (tránh dual-writer `atz-ssi-stream`).

---

## Debug overlay — dùng nhanh

| | dev.atz.vn | atz.vn |
|--|------------|--------|
| Bật | `config/debug_overlay.yaml` · `PB_DEBUG_UI=1` | `ATZ_DEBUG_OVERLAY=1` · groups Authentik |
| Hotkey | ⌘⇧D / Ctrl⇧D | ⌘⇧D / Ctrl⇧D |
| Copy | Panel → **Copy JSON** (`ui_ref`, hints, `err_codes`) | Giống |
| Tắt | `PB_DEBUG_UI=0` hoặc Esc | `ATZ_DEBUG_OVERLAY=0` |

Config chung: [`config/debug_overlay.yaml`](../../config/debug_overlay.yaml) — `surfaces.priceboard` / `surfaces.atz`.

---

## VPS trạng thái (2026-10-25)

| Stack | Branch @ HEAD | Ghi chú |
|-------|---------------|---------|
| `atz_priceboard` (dev) | `781ec9e` | mount `backend/` + `frontend/` — pull + restart api đủ cho JS/Python |
| `vnstocks` (prod) | `781ec9e` | **Cần rebuild image** khi đổi `src/atz` hoặc Dockerfile |

```bash
# Dev priceboard
docker compose -f docker-compose.dev.yml restart api ssi-worker

# Prod app (sau pull + đổi src/Dockerfile)
docker compose build vnstocks && docker compose up -d --no-deps vnstocks

# Log ERR-PB
docker compose -f docker-compose.dev.yml logs --tail=200 api ssi-worker 2>&1 | grep -E 'ERR-PB|PB-'
```

---

## Next (ưu tiên)

### P0 — phiên GD (~09:00 ICT)
1. [P0_LIVE_VERIFY.md](P0_LIVE_VERIFY.md): tick live · volume gate · spark · Inspect pick ô HPG/bid1.  
2. Capture SSI → điền [P1 §4](../specs/PRICEBOARD_P1_DEPTH_NN.md) → user chọn `2a` partial parse.

### P0.5 — git
1. Merge / theo dõi PR #4.  
2. Commit rule `dev-atz-scope.mdc` + AGENTS nếu user muốn đồng bộ repo.

### P1 — depth / NN
1. Code map theo §4 sau capture.  
2. Mở rộng `ui_catalog.json` + hints file:line (overlay v2 — nếu user yêu cầu).

### P2 / backlog
- Panel “lỗi gần đây” (ERR-PB + origin) trên dev.atz.vn.  
- `FILTER_SCORING_HUONG1.md` (priceboard screener).  
- Spark cột equity (khi user chọn).

---

## Câu mở chat / Cloud Agent

```
HANDOFF_NEXT_CHAT

@docs/bots/HANDOFF_NEXT_CHAT.md
feature/priceboard-debug-trace @ 781ec9e
dev: https://dev.atz.vn · prod app: https://atz.vn
SSH: root@112.213.88.230 → /opt/vnstocks
Overlay: pb-ui (dev) · atz-ui (prod) · ⌘⇧D · Copy JSON
Debug logs: docs/specs/PRICEBOARD_DEBUG.md (ERR-PB-* + origin)
Không đụng stream.d / sshd / UFW.
```
