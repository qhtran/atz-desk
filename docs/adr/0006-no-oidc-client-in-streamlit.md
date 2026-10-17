# ADR 0006 — Không OIDC Client trong Streamlit (bổ sung ADR 0003)

- **Status:** Accepted (Master Architect, 2026-10-17)
- **Context:** Đề xuất Gemini (prompt Architect/Executor) khuyến khích tích hợp OpenID Connect *trong* app atz.vn: authorization code, JWT session, `CLIENT_SECRET`, Social Login SDK-style, short-lived Access Token trong Streamlit.
- **Related:** ADR 0003 (Account UX / forward-auth), ADR 0004 (trading profile SQLite), `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md`

## Quyết định

1. **Giữ** mô hình hiện tại: nginx `auth_request` → Authentik outpost → header `X-authentik-*` → [`src/atz/engine/identity.py`](../../src/atz/engine/identity.py).
2. **Không** triển khai OIDC Client library trong Streamlit / container `vnstocks` (không Authlib/oauth app flow, không lưu Access/Refresh Token trong `st.session_state` làm phiên chính).
3. **Social Login** (Google/Facebook): cấu hình **trên Authentik** (Sources + Flows). App **không** nhúng SDK bên thứ ba; sau login vẫn chỉ nhận headers forward-auth.
4. **Brand / Custom Flow** Authentik: task infra riêng (`user_confirmed_infra: yes`); không clone Authentik UI vào Streamlit.
5. Đổi sang OIDC Client trong app **chỉ** khi chủ repo mở ADR mới thay/đính chính 0003 + 0006 (big-bang auth), không phải task Executor thường.

## Lý do

| Gemini literal | atz.vn thực tế |
|----------------|----------------|
| App đổi code → token → session cookie | Phiên = cookie outpost; không có access token trong Streamlit (ADR 0003) |
| `CLIENT_ID`/`SECRET` trong app | Tăng bề mặt secret; trùng với outpost đã có |
| Hai lớp phiên (outpost + app JWT) | Logout/SLO lệch; khó debug |
| Streamlit giữ refresh token | Process/websocket Streamlit không phải OIDC RP điển hình |
| Social trong prompt app | Đúng chỗ là Authentik IdP proxy — app không cần SDK |

Phase 1 Account UX đã ship (headers-only, deep-link password/MFA, sign_out outpost). Forward-auth đủ cho ~100 users.

## Hệ quả / NON-goals cho Agent

**Architect / Executor MUST NOT:**

- Thêm OIDC client dependency hoặc callback route “login OIDC” trên atz.vn trừ ADR mới.
- Hardcode hoặc commit secrets OAuth/OIDC.
- Đụng nginx stream / sshd / UFW / Authentik compose trừ brief + `user_confirmed_infra: yes`.

**Architect / Executor MAY:**

- Đọc/hiển thị identity từ headers; BFF Phase 2 server-side theo spec 0003 (brief riêng).
- Brief infra: Authentik Social Sources, brand CSS — không đụng app OIDC.

## Bus & prompt

- Blueprint vận hành: [`PROGRESS.md`](../../PROGRESS.md) (không bắt buộc `TODO.md` / `ARCHITECTURE_PLAN.md` song song).
- Prompt Architect Identity: ghi rõ forward-auth + ADR 0003/0006; cấm greenfield OIDC client.

## References

- Phản biện nội bộ: plan «OIDC Gemini Critique» (2026-10-17)
- `docs/adr/0003-account-ux-authentik-bff.md`
- `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md`
- `docs/bots/HANDOFF_NEXT_CHAT.md`
