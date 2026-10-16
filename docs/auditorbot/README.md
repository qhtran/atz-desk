# AuditorBot ↔ repo (survey)

Tổng điều phối đa-bot: [`docs/bots/ORCHESTRATION.md`](../bots/ORCHESTRATION.md).

## Vai trò

| Vai trò | Bot | Việc |
|--------|-----|------|
| **Auditor** | AuditorBot (Grok + computer use) | Duyệt **atz.vn** và **fireant.vn**, ghi báo cáo vào inbox |
| **Orchestrator** | Cursor | Đọc báo cáo → giao việc tiếp (thường qua **VPSbot**) hoặc hỏi user |
| **Coder** | VPSbot | Code / deploy theo brief (xem `docs/bots/vpsbot/`) |

## Thư mục

```
docs/auditorbot/
  README.md
  PROTOCOL.md
  REPORT_TEMPLATE.md
  PROMPT_FOR_AUDITORBOT.md   # copy cho Grok
  inbox/                     # báo cáo mới (chưa xử lý)
  reports/                   # đã xử lý + Resolution
```

**Tên file:** `YYYYMMDD-HHMM-<site>-<topic>.md`

## Vòng đời

1. Cursor/user giao survey → AuditorBot dùng `PROMPT_FOR_AUDITORBOT.md`
2. AuditorBot push báo cáo → `inbox/`
3. Cursor đọc → brief VPSbot (hoặc tự sửa nếu user chọn)
4. Sau xong: chuyển `inbox/` → `reports/` + mục Resolution

## Browser Cursor

Chỉ để Orchestrator **verify ngắn** sau deploy — không thay AuditorBot survey dài.
