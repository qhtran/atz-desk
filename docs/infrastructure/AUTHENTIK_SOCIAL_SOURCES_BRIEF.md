# Brief — Social Login trên Authentik (SSO đa nguồn + duyệt admin)

- **Status:** Ready — human đã authorize plan SSO pending-approve; apply VPS khi `user_confirmed_infra: yes` + OAuth env
- **Owner:** Infra / VPSbot / Exe1 (SSH Authentik stack) — **không** Executor app `vnstocks` (OIDC)
- **ADRs:** 0003 (forward-auth), **0006** (cấm OIDC client Streamlit), 0007 (deploy gate)
- **PROGRESS:** T-220 (Sources + enrollment), T-221 (smoke approve)

## Mục tiêu

Cho phép đăng nhập **Google / Facebook / OIDC generic** (và IdP tương tự) **qua Authentik Sources**, rồi vào `atz.vn` như hiện tại (nginx `auth_request` → outpost → `X-authentik-*`).

**Bảo mật (chốt):** SSO chỉ **tạo identity** từ claim IdP. User mới:

1. `is_active=false`
2. Group **`cho-duyet`**
3. **Chưa** vào được `atz.vn` (policy `atz-user-is-active` trên app `atz`)
4. Admin/mod **Active** (+ gỡ/đổi group nếu cần) → mới vào site

App Streamlit **không** đổi auth model: vẫn [`identity.py`](../../src/atz/engine/identity.py) đọc headers.

```text
User → auth.atz.vn (Social) → IdP → Authentik tạo user inactive/cho-duyet
     → message chờ duyệt (không login stage)
Admin → Directory → Users → Active
User → atz.vn → auth_request → headers → Streamlit
```

## Phạm vi (in)

1. Authentik **Sources**: Google, Facebook, template **OIDC generic**; client id/secret chỉ trong `/opt/authentik/.env`.
2. Flow enrollment SSO riêng: [`deploy/authentik/blueprints/atz-source-enrollment.yaml`](../../deploy/authentik/blueprints/atz-source-enrollment.yaml) — write inactive + `cho-duyet`, **không** User Login stage.
3. Gắn Sources vào identification stage + `enrollment_flow` = `atz-source-enrollment` — [`atz-social-sources.yaml`](../../deploy/authentik/blueprints/atz-social-sources.yaml).
4. Giữ policy binding `atz-user-is-active` trên Application `atz` (đã có trong enrollment local).
5. (Tuỳ chọn cùng cửa sổ) Brand / Custom CSS login Authentik — **không** đụng nginx stream / sshd / UFW.
6. Smoke: SSO → pending block → admin activate → `atz.vn` OK (checklist bên dưới).

## Phạm vi (out / NON-goals)

- Không thêm Authlib / OIDC callback / JWT session trong Streamlit.
- Không `CLIENT_SECRET` trong container `vnstocks` hoặc git.
- Không browser gọi Authentik Admin API.
- Không nhét trading prefs vào Authentik attributes (ADR 0004).
- Không auto-approve mọi SSO.
- Không mở task Executor app kiểu «integrate Google Login».

## Preconditions

| Điều kiện | Ghi chú |
|-----------|---------|
| `user_confirmed_infra: yes` | Scope: Authentik Sources + blueprints custom; **không** stream/sshd/UFW |
| Credentials OAuth | Google Cloud + Meta Developer (+ OIDC IdP khi có) → env Authentik, không commit |
| Forward-auth ổn | Provider/outpost `atz.vn` giữ nguyên trừ gắn Source |

## Env (chỉ trên VPS — không commit giá trị)

Thêm vào `/opt/authentik/.env` (xem [`.env.example`](../../deploy/authentik/.env.example)):

```text
AUTHENTIK_SOURCES_GOOGLE_CLIENT_ID=
AUTHENTIK_SOURCES_GOOGLE_CLIENT_SECRET=
AUTHENTIK_SOURCES_FACEBOOK_CLIENT_ID=
AUTHENTIK_SOURCES_FACEBOOK_CLIENT_SECRET=
AUTHENTIK_SOURCES_OIDC_CLIENT_ID=
AUTHENTIK_SOURCES_OIDC_CLIENT_SECRET=
AUTHENTIK_SOURCES_OIDC_OIDC_URL=   # well-known URL
AUTHENTIK_SOURCES_OIDC_AUTHORIZATION_URL=
AUTHENTIK_SOURCES_OIDC_TOKEN_URL=
AUTHENTIK_SOURCES_OIDC_PROFILE_URL=
```

Blueprint OIDC: `atz-social-oidc-generic.yaml` (cần authorization/token/profile URL).


**Redirect URI** (Google/Meta/OIDC app console) — slug Source phải khớp:

- `https://auth.atz.vn/source/oauth/callback/google/`
- `https://auth.atz.vn/source/oauth/callback/facebook/`
- `https://auth.atz.vn/source/oauth/callback/oidc-generic/`

## Apply trên VPS (Exe1 / VPSbot)

```sh
# 1) Sync blueprints từ repo (copy file, không commit .env)
scp deploy/authentik/blueprints/atz-source-enrollment.yaml \
    deploy/authentik/blueprints/atz-social-sources.yaml \
    root@HOST:/opt/authentik/blueprints/

# 2) Điền OAuth env vào /opt/authentik/.env (chmod 600)
# 3) Restart worker/server để nạp blueprint + env (không down -v)
cd /opt/authentik && docker compose up -d --force-recreate server worker

# 4) Admin UI: Directory → Federation — bật Source khi env đã có secret
#    Identification stage phải liệt kê Sources (blueprint cố gắng gắn)
```

Nếu blueprint OIDC/Google field lệch Authentik 2026.8: tạo Source bằng Admin UI theo brief này, vẫn gắn `enrollment_flow` = `atz-source-enrollment`.

## Admin phê duyệt (giống enrollment local)

1. `https://auth.atz.vn/if/admin/` → Directory → Users  
2. Lọc group `cho-duyet` hoặc Active=off  
3. Bật **Active** → Update  
4. (Khuyến nghị) chuyển group sang nhóm được phép dùng app  
5. User đăng nhập lại Social → vào `https://atz.vn`

## Acceptance / smoke checklist

- [ ] Nút Google / Facebook trên login Authentik (OIDC generic: hiện khi Source enabled + env)
- [ ] User mới SSO → account tồn tại; `is_active=false`; group `cho-duyet`
- [ ] Truy cập `https://atz.vn` **bị chặn** (denied / không vào Streamlit)
- [ ] Admin activate → vào được; header `X-authentik-*`; trang Tài khoản OK
- [ ] Logout outpost vẫn kết thúc phiên
- [ ] Không sửa `src/atz` auth; không đụng stream/sshd/UFW
- [ ] OIDC generic: blueprint/template sẵn; bật khi có issuer + credentials

## Liên kết

- `docs/adr/0006-no-oidc-client-in-streamlit.md`
- `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md`
- `docs/infrastructure/VPS_NETWORK.md`
- `deploy/authentik/README.md`
- `PROGRESS.md` — T-220 / T-221
