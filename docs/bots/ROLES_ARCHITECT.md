# Phân vai Wave hiện tại

| Vai | Ai | Làm | Không làm |
|-----|-----|-----|-----------|
| **Kiến trúc sư / Orchestrator** | Cursor (chat này) | Thiết kế, ưu tiên, brief, **tự** `git pull/push`, đọc outbox, chốt hướng, chuẩn DoD | Không viết feature app lớn; không SSH deploy thay VPSbot |
| **Coder / Ops** | VPSbot | Code, test module, commit, deploy SSH:443 | Không đổi kiến trúc ngoài brief |
| **Tester / Survey** | AuditorBot | Kiểm thử chấp nhận trên web (atz vs FireAnt), regression UI, báo P0/P1/P2 | Không sửa code production |

Luồng: Architect push brief → bot poll → Architect tự pull đọc kết quả → brief tiếp hoặc Resolution.

## Quyền tự chạy lệnh (Orchestrator)

Chủ repo đã chốt: **Cursor tự chạy lệnh**, không hỏi user gõ cmd/code.

| Được | Không được |
|------|------------|
| `git` trong repo, đọc/ghi file **trong** project, test local, push brief/docs | Xóa phá dữ liệu/repo (`rm -rf`, force push, reset hard mất commit chưa backup) |
| `pull` định kỳ kiểm tra outbox bot | Sửa / đọc file **ngoài** project (home secrets, `/etc`, máy khác) trừ khi brief + user xác nhận |
| Commit + push docs/brief orchestration | Commit `.env` / secret; đụng nginx/SSH/firewall trên VPS (thuộc VPSbot + gate) |
