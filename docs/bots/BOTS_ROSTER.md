# Roster bot (atz.vn / vnstocks)

Nguồn chủ repo bổ sung 2026-10-17. Orchestrator: Cursor.  
Cập nhật khi thêm/đổi vai — không hardcode secret.

| Bot | Vai trò | Trạng thái kênh git | Ghi chú |
|-----|---------|---------------------|---------|
| **VPSBot** | Code và deploy trên VPS atz.vn; nhận việc qua brief trong `inbox/` của repo | **Active** — `docs/bots/vpsbot/` | SSH:443; Docker/nginx/Redis/SQLite theo PROTOCOL |
| **AuditorBot** | So sánh atz.vn với FireAnt về kiến trúc và UI/UX; **chỉ đọc, không sửa** | **Active** — `docs/auditorbot/` | Computer use / survey; tasks → inbox báo cáo |
| **SecConfBot** | Kiểm tra bảo mật và cấu hình sau mỗi thay đổi trên VPS | **Planned** — `docs/bots/secconfbot/` | Chạy sau deploy/outbox VPSbot; không sửa trừ brief + confirm |
| **Stock Screening Agent** | Sàng lọc cổ phiếu theo tiêu chí mentor: CANSLIM, ngành, mẫu hình, dòng tiền | **Planned** — `docs/bots/screening/` | Output báo cáo/markdown hoặc signal — không deploy infra |
| **DailyStockNews** | Tóm tắt tin tức và biến động thị trường mỗi sáng và tối | **Planned** — `docs/bots/dailystocknews/` | Lịch sáng/tối; chỉ đọc nguồn tin / RSS |
| **YSradar Portfolio Agent** | Đọc và phân tích Portfolio, Bảng giá trên YSradar (Yuanta) | **Planned** — `docs/bots/ysradar/` | Chỉ đọc UI/data Yuanta; không sửa atz trừ brief riêng |

## Quy tắc chung

- Brief / kết quả ưu tiên qua **GitHub** (inbox → outbox hoặc reports).
- Cursor = kiến trúc sư: brief ngắn, poll git, không đụng file ngoài project.
- Bot **Active** đã có PROTOCOL/PROMPT; bot **Planned** chỉ có stub thư mục đến khi mở sóng.
