# Brief — Social Login trên Authentik (không OIDC Client trong app)

- **Status:** Ready when human + `user_confirmed_infra: yes`
- **Owner:** Infra / VPSbot (SSH Authentik stack) — **không** Executor app `vnstocks`
- **ADRs:** 0003 (forward-auth), **0006** (cấm OIDC client Streamlit)

## Mục tiêu

Cho phép đăng nhập Google / Facebook (và nguồn tương tự) **qua Authentik**, rồi vào `atz.vn` như hiện tại (nginx `auth_request` → outpost → `X-authentik-*`).

App Streamlit **không** đổi auth model: vẫn [`identity.py`](../../src/atz/engine/identity.py) đọc headers.

## Phạm vi (in)

1. Authentik **Sources** (OAuth/OIDC IdP bên thứ ba): tạo Source Google/Facebook; client id/secret chỉ trong env Authentik.
2. Gắn Source vào **identification / authentication flow** đang dùng bởi forward-auth provider của `atz.vn`.
3. (Tuỳ chọn) Brand / Custom CSS login Authentik — cùng cửa sổ infra với T-220; **không** đụng nginx stream / sshd / UFW.
4. Smoke: login social → redirect về `atz.vn` → header có username/email; trang Tài khoản hiển thị đúng.

## Phạm vi (out / NON-goals)

- Không thêm Authlib / OIDC callback / JWT session trong Streamlit.
- Không `CLIENT_SECRET` trong container `vnstocks` hoặc repo.
- Không browser gọi Authentik Admin API (spec Account UX).
- Không nhét trading prefs vào Authentik attributes (ADR 0004).
- Không mở task Executor app kiểu «integrate Google Login».

## Preconditions

| Điều kiện | Ghi chú |
|-----------|---------|
| `user_confirmed_infra: yes` | Human chọn rõ scope Authentik |
| Credentials OAuth | Google Cloud / Meta Developer — chủ repo cung cấp secret qua env, không commit |
| Forward-auth provider ổn | Blueprint / outpost hiện tại không đổi trừ cần gắn Source |

## Acceptance (infra)

- [ ] Source Google (và/hoặc Facebook) `enabled` trên Authentik
- [ ] Flow login có nút Social; sau auth vào được `atz.vn`
- [ ] Logout outpost vẫn kết thúc phiên
- [ ] Không thay đổi code `src/atz` trừ documentation
- [ ] Không đụng stream/sshd/UFW

## Liên kết

- `docs/adr/0006-no-oidc-client-in-streamlit.md`
- `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md`
- `docs/infrastructure/VPS_NETWORK.md`
- `PROGRESS.md` — task infra riêng (ví dụ mở rộng T-220); **không** làm OIDC app
