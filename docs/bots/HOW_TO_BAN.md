# Bạn làm gì để hai bot biết có việc

Không cần GitHub Actions. Hai bot **tự mở hộp việc trên GitHub** mỗi vài phút.

## Hình ảnh nhanh

```
Bạn / Cursor viết file “việc” → git push
        ↓
Bot (đang chạy prompt) mỗi ~5 phút: git pull → thấy file mới → làm → push kết quả
        ↓
Bạn bảo Cursor: “pull, đọc kết quả”
```

## Làm một lần (khởi động bot)

Chỉ cần khi phiên bot chưa mở. Orchestrator đã push việc lên GitHub.

1. Mở **AuditorBot** → paste khối trong `docs/auditorbot/PROMPT_FOR_AUDITORBOT.md`.
2. Mở **VPSbot** → paste khối trong `docs/bots/vpsbot/PROMPT_FOR_VPSBOT.md`.
3. Giữ hai phiên mở — chúng tự `git pull` và lấy việc.

## Mỗi khi có việc mới

### Giao AuditorBot (survey web)

1. Tạo file theo mẫu `docs/auditorbot/TASK_TEMPLATE.md`
2. Đặt vào: `docs/auditorbot/tasks/YYYYMMDD-HHMM-<topic>.md`
3. `git add` + `commit` + `push` lên `main` (hoặc bảo Cursor làm)

→ AuditorBot thấy file trong `tasks/` → survey → push báo cáo vào `docs/auditorbot/inbox/`

### Giao VPSbot (code / deploy / docker)

1. Tạo file theo mẫu `docs/bots/vpsbot/TASK_TEMPLATE.md`
2. Đặt vào: `docs/bots/vpsbot/inbox/YYYYMMDD-HHMM-<topic>.md`
3. `git add` + `commit` + `push`

→ VPSbot thấy file → làm → push code + `docs/bots/vpsbot/outbox/…-DONE.md`

## Bạn / Cursor kiểm tra kết quả

```bash
git pull
```

- Auditor: đọc `docs/auditorbot/inbox/`
- VPSbot: đọc `docs/bots/vpsbot/outbox/`

## Nếu bot “không thấy việc”

| Nguyên nhân | Cách xử lý |
|-------------|------------|
| Bot đã tắt / hết phiên | Paste lại PROMPT, bảo: «poll theo PROTOCOL» |
| Brief chưa push GitHub | `git push` rồi đợi tối đa ~5 phút |
| Sai thư mục | Auditor = `tasks/`; VPSbot = `inbox/` |
| Đã có outbox cùng tên | Bot bỏ qua (coi như xong) — tạo brief stem mới |

## Không làm

- Không cần Actions để “đánh thức” bot.
- Không cần chat Cursor ↔ bot; chỉ qua file GitHub.
