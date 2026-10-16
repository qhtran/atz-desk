# Phân vai Wave hiện tại

| Vai | Ai | Làm | Không làm |
|-----|-----|-----|-----------|
| **Orchestrator** | Cursor | Giữ liên lạc (brief, `git pull`/`push`, đọc outbox khi cần); tự chạy lệnh **trong repo**; chốt hướng | Code/survey/deploy nặng (giao bot); **tuyệt đối không** đụng file ngoài project |
| **Coder / Ops** | VPSbot | Code, test, commit, deploy SSH:443 | Đổi kiến trúc ngoài brief |
| **Tester** | AuditorBot | Survey/regression web → inbox | Sửa code production |

**Token:** việc nặng → 2 bot. Cursor vẫn **giữ nhịp**: tự pull/kiểm tra kết quả, brief tiếp — không nhờ user gõ cmd.

## Ranh giới bắt buộc

| Được (trong `/Users/…/vnstocks` hoặc clone repo) | Cấm |
|--------------------------------------------------|-----|
| git, brief/docs, đọc inbox/outbox, test local | Mọi path **ngoài** project (home secrets, `/etc`, `.ssh` private, máy khác…) |
| Commit + push docs/brief | Force push, xóa phá repo, commit `.env`/secret |
| | nginx/SSH/firewall trên VPS (VPSbot + gate) |
