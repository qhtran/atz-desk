# Roster bot (atz.vn / vnstocks)

Cập nhật **2026-10-17**: chủ repo tạm **không** dùng bot trả phí để code/deploy.  
**Cursor** tự triển khai trong repo (+ deploy khi được giao). Chỉ giữ bot **kiểm tra hình / UI**.

| Bot | Vai trò | Trạng thái |
|-----|---------|------------|
| **Cursor (Orchestrator + Coder)** | Thiết kế, code, test, commit/push, deploy khi cần | **Active — làm hết** |
| **AuditorBot** | So sánh atz vs FireAnt (hình / UI/UX); **chỉ đọc** | **Active — giữ** (survey hình) |
| **VPSBot** | Code/deploy VPS | **Paused** — không giao việc mới |
| **SecConfBot** | Sec/config sau đổi VPS | **Paused** |
| **Stock Screening Agent** | Sàng CANSLIM / ngành / mẫu / dòng tiền | **Paused** |
| **DailyStockNews** | Tin sáng/tối | **Paused** |
| **YSradar Portfolio Agent** | Đọc YSradar | **Paused** |

## Quy tắc

- Brief `vpsbot/inbox` không dùng cho triển khai mới (trừ khi chủ repo bật lại).
- Auditor: `docs/auditorbot/tasks/` → báo cáo `inbox/`.
- Cursor: tự lệnh trong project; **cấm** file ngoài project; không đụng nginx stream/SSH trừ confirm.
