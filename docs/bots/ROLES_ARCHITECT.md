# Phân vai Wave hiện tại

| Vai | Ai | Làm | Không làm |
|-----|-----|-----|-----------|
| **Kiến trúc sư / Orchestrator** | Cursor (chat này) | Thiết kế, ưu tiên, brief, đọc outbox, chốt `1a/1b`, chuẩn DoD | Không viết feature app lớn; không SSH deploy thay VPSbot |
| **Coder / Ops** | VPSbot | Code, test module, commit, deploy SSH:443 | Không đổi kiến trúc ngoài brief |
| **Tester / Survey** | AuditorBot | Kiểm thử chấp nhận trên web (atz vs FireAnt), regression UI, báo P0/P1/P2 | Không sửa code production |

Luồng: Architect push brief → bot poll → Architect đọc kết quả → brief tiếp hoặc Resolution.
