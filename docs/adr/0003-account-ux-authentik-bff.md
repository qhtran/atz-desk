# ADR 0003 — Account UX vs Authentik (Forward Auth)

- **Status:** Accepted (kiến trúc sư Cursor, 2026-10-17)
- **Context:** ~100 users; Authentik độc lập Docker; `atz.vn` bảo vệ bằng nginx `auth_request` + outpost; header `X-authentik-*` → Streamlit. UX dashboard Authentik lệch theme VANTIQ.

## Quyết định

**Không** gọi Authentik API từ browser.  
**Có** trang Tài khoản trên site chính (theme VANTIQ) + **BFF mỏng** (server-side) cho thao tác cần API; thao tác nhạy cảm (đổi mật khẩu / TOTP) ưu tiên **deep-link flow Authentik đã brand**, không clone full User Interface Authentik.

## Lý do (tóm tắt)

Hiện tại không có access token OIDC trong Streamlit; phiên là cookie outpost. Gọi API từ FE = CORS + lộ token + lệch mô hình bảo mật. Quy mô 100 users: BFF đủ nhẹ.

## Hệ quả

- Module mới: UI Account + BFF proxy scoped; logout outpost + end-session Authentik.
- Không sửa sshd/firewall; nginx/Authentik chỉ khi `user_confirmed_infra: yes`.
- Spec triển khai: mục «Technical Specification» trong chat / brief VPSbot.
