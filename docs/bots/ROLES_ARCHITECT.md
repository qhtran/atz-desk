# Phân vai Wave hiện tại

| Vai | Ai | Làm | Không làm |
|-----|-----|-----|-----------|
| **Orchestrator** | Cursor | **Liên lạc = poll git** (kéo `main`, xem bot đã gửi báo cáo chưa); brief ngắn; tự chạy lệnh trong repo | Code/survey/deploy nặng; **cấm** file ngoài project |
| **Coder / Ops** | VPSbot | Code → outbox DONE/FAIL | Ngoài brief |
| **Tester** | AuditorBot | Survey → `docs/auditorbot/inbox/` | Sửa code production |

## Liên lạc (định nghĩa)

Poll GitHub định kỳ trong repo:

1. `git pull --ff-only origin main`
2. Xem mới trong:
   - `docs/bots/vpsbot/outbox/` (`*-DONE.md` / `*-FAIL.md`)
   - `docs/auditorbot/inbox/` (báo cáo survey)
3. Có file mới → tóm tắt ngắn + brief tiếp nếu P0  
   Không có → ngủ đến chu kỳ sau (không đốt token làm việc khác)

Chu kỳ gợi ý: **~30 phút**. Chỉ thao tác trong project.

## Cấm

Force push · xóa phá · `.env`/secret · path ngoài project · nginx/SSH VPS (thuộc VPSbot).
