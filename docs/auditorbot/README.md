# AuditorBot ↔ repo (survey)

Tổng điều phối: [`docs/bots/ORCHESTRATION.md`](../bots/ORCHESTRATION.md)  
**Bạn làm gì:** [`docs/bots/HOW_TO_BAN.md`](../bots/HOW_TO_BAN.md)

## Vai trò

| Vai trò | Bot | Việc |
|--------|-----|------|
| **Auditor** | AuditorBot | Poll `tasks/` → survey web → ghi `inbox/` |
| **Orchestrator** | Cursor | Push task → đọc báo cáo → giao VPSbot |
| **Coder** | VPSbot | Code / deploy (`docs/bots/vpsbot/`) |

## Thư mục

```
docs/auditorbot/
  tasks/          # hộp việc (Orchestrator / bạn push)
  inbox/          # báo cáo mới từ AuditorBot
  reports/        # đã xử lý + Resolution
  TASK_TEMPLATE.md
  PROMPT_FOR_AUDITORBOT.md
```

## Vòng đời

1. Paste `PROMPT_FOR_AUDITORBOT.md` → giữ phiên mở (bot tự poll).
2. Push file vào `tasks/`.
3. AuditorBot push báo cáo → `inbox/`.
4. Cursor đọc → brief VPSbot; sau đó `inbox/` → `reports/`.
