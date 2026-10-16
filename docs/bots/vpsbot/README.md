# VPSbot

Coder + **ops/infra** cho atz.vn: app code, **Docker/Compose**, deploy VPS, Redis/SQLite, nginx/server setup theo brief.

**Kênh:** GitHub (brief/code/outbox) + **SSH** (mọi lệnh trên VPS).

| File | Mục đích |
|------|----------|
| `PROTOCOL.md` | Phạm vi, Docker/nginx/db, rủi ro P0, DoD |
| `PROMPT_FOR_VPSBOT.md` | Prompt khởi động phiên |
| `TASK_TEMPLATE.md` | Mẫu brief inbox |
| `inbox/` | Brief từ Orchestrator (push GitHub) |
| `outbox/` | DONE/FAIL sau khi VPSbot push |

Orchestrator: Cursor — xem `docs/bots/ORCHESTRATION.md`.
