# Phân vai Wave hiện tại

| Vai | Ai | Làm | Không làm |
|-----|-----|-----|-----------|
| **Architect + Coder + Ops** | Cursor | Thiết kế + **tự code/test/deploy**; poll git nếu còn Auditor | **Cấm** file ngoài project |
| **Auditor hình/UI** | AuditorBot | Survey atz vs FireAnt (chỉ đọc) | Sửa code |
| **VPSBot & bot code khác** | — | **Paused** (phí Grok) | — |

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
