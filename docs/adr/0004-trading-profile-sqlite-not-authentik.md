# ADR 0004 — Trading Profile trong SQLite (không Authentik)

- **Status:** Accepted hướng; **Cursor tự triển khai** (không giao VPSBot) — chờ chọn phạm vi 1a/1b
- **Context:** Cần thuộc tính trade cá nhân (rủi ro, filter ưu tiên, vốn…). Gemini đề xuất bảng `user_trading_profiles` trên `signals.db`.

## Quyết định kiến trúc (hội đồng Cursor)

1. **Đồng ý Gemini:** Authentik = identity only; trade prefs **không** nhét User Attributes Authentik.
2. **Chỉnh Gemini:** Không tạo bảng song song lệch PK. Tái sử dụng / mở rộng schema hiện có:
   - `users.id` (INTEGER) + `username` (map từ header Authentik)
   - `users.cai_dat_chung` (JSON) và/hoặc `user_filter_configs` đã có
   - Sổ vốn: nâng từ CSV dùng chung → per-user trong SQLite (gap thật)
3. Load profile **một lần / session** hoặc khi user bấm Lưu — **không** ghi SQLite mỗi tick fragment 1.5–3s realtime.

## Không làm

- Gọi Authentik API mỗi lần đổi slider
- Phình OIDC token bằng trade attrs
- Đụng nginx / Authentik / SSH
