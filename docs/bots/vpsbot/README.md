# VPSbot

Coder + **ops/infra** cho atz.vn: app code, **Docker/Compose**, deploy VPS, Redis/SQLite, nginx/server setup theo brief.

**Kênh:** GitHub (hộp việc/outbox) + **SSH qua cổng 443**.  
**Bạn làm gì:** [`../HOW_TO_BAN.md`](../HOW_TO_BAN.md)

| File | Mục đích |
|------|----------|
| `PROTOCOL.md` | Phạm vi, poll, Docker/nginx/db, rủi ro P0 |
| `PROMPT_FOR_VPSBOT.md` | Prompt khởi động (có vòng poll) |
| `TASK_TEMPLATE.md` | Mẫu brief |
| `inbox/` | Hộp việc (Orchestrator push) |
| `outbox/` | DONE/FAIL |

Orchestrator: `docs/bots/ORCHESTRATION.md`.
