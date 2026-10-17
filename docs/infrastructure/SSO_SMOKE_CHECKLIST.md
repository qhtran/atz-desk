# Smoke — SSO pending approve (T-221)

Chạy sau khi Exe1/VPSbot apply blueprint + (nếu có) OAuth env. Báo cáo vào outbox + PROGRESS.

## Precheck

- [ ] `atz-source-enrollment` flow exists (Admin → Flows)
- [ ] Sources Google / Facebook / OIDC-generic exist (enabled chỉ khi secret có)
- [ ] Application `atz` vẫn bind policy `atz-user-is-active`
- [ ] Không đụng nginx stream / sshd / UFW

## A — User mới SSO (pending)

1. Browser sạch / cửa sổ ẩn danh → mở login Authentik (qua `atz.vn` hoặc `auth.atz.vn`)
2. Chọn Google hoặc Facebook
3. Hoàn tất IdP → thấy message **chờ quản trị duyệt**
4. Admin → Users: user mới `is_active=false`, group `cho-duyet`
5. Mở `https://atz.vn` → **không** vào Streamlit (denied / redirect login)

**Pass A nếu:** 3–5 đúng.

## B — Admin approve

1. Admin Active user (+ optional đổi group)
2. User login Social lại
3. Vào `https://atz.vn` → Streamlit; trang Tài khoản có username/email từ header
4. Logout outpost → mở lại `atz.vn` → bắt login

**Pass B nếu:** 2–4 đúng.

## C — OIDC generic (khi có IdP)

- [ ] Source enabled + discovery URL OK
- [ ] Cùng semantics A→B (pending rồi approve)

Nếu chưa có credentials OIDC: ghi **Skip C — template only** (không Fail toàn bộ T-221 nếu A+B Pass).

## Kết quả ghi outbox

```text
T-221 result: Pass|Fail|Partial
A: Pass|Fail
B: Pass|Fail
C: Pass|Fail|Skip
notes: …
```
