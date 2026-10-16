# Phân vai Wave hiện tại

| Vai | Ai | Làm | Không làm |
|-----|-----|-----|-----------|
| **Orchestrator** | Cursor | Brief ngắn, `git push` hộp việc, `pull` đọc outbox khi user/bot báo xong, chốt `1a/1b` | **Không** code feature; **không** survey web; **không** SSH; **không** loop poll đốt token |
| **Coder / Ops** | VPSbot | Code, test, commit, deploy SSH:443 | Đổi kiến trúc ngoài brief |
| **Tester** | AuditorBot | Survey/regression web, báo cáo inbox | Sửa code production |

**Tiết kiệm token Cursor:** việc nặng → 2 bot. Cursor chỉ vài đoạn brief + tóm tắt kết quả.

Luồng: brief ngắn → push → bot poll → user/báo xong → Cursor pull đọc → brief tiếp (nếu cần).

## Lệnh trong repo

Được: git trong project, brief/docs.  
Không: xóa phá, force push, file ngoài project, secret, nginx/SSH trên VPS.
