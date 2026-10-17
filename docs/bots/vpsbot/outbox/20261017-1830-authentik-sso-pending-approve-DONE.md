# Outbox — Authentik SSO pending approve (T-220 / T-221)

- **ID:** `20261017-1830-authentik-sso-pending-approve-DONE.md`
- **result:** **Pass** (infra apply) / **Partial** (live Google/FB SSO — chờ OAuth secrets)
- **owner:** Cursor implement session (plan SSO)
- **user_confirmed_infra:** yes (Authentik only)

## Đã làm

1. Sync blueprints → `/opt/authentik/blueprints/`:
   - `atz-source-enrollment.yaml` — flow `atz-source-enrollment` (inactive + `cho-duyet`, no login stage)
   - `atz-social-sources.yaml` — Google + Facebook (`enabled=false`, placeholder secrets)
   - `atz-social-oidc-generic.yaml` — OIDC generic (`enabled=false`)
2. Append `AUTHENTIK_SOURCES_*` keys (empty) vào `/opt/authentik/.env`
3. `ak apply_blueprint` Google/FB/OIDC OK; identification sources: `google`, `facebook`, `oidc-generic`
4. nginx reload sau recreate (stale upstream IP) → `atz.vn` / `auth.atz.vn` **302** lại
5. Policy smoke: inactive user → `atz-user-is-active` **False**; active → **True**; cleanup user

## Smoke checklist (SSO_SMOKE_CHECKLIST.md)

| Mục | Kết quả |
|-----|---------|
| A (SSO IdP thật) | **Skip** — Sources `enabled=false` đến khi human dán client id/secret |
| A' (policy proxy) | **Pass** — inactive blocked / active allowed |
| B (admin activate + live SSO) | **Skip** — cần A |
| C (OIDC live) | **Skip** — template only |
| Logout / site up | **Pass** — public 302 Authentik |

## Human còn lại

1. Tạo OAuth apps Google/Meta; điền secrets vào `/opt/authentik/.env` hoặc Admin UI  
2. Enable Sources `google` / `facebook`  
3. Chạy lại checklist A+B bằng browser  

## CẤM đã tôn trọng

- Không đụng nginx stream / sshd / UFW  
- Không `down -v` / xóa volume  
- Không commit secrets  
