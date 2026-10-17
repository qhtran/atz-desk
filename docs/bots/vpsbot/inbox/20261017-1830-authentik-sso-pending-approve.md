# Brief VPSbot / Exe1 — Authentik SSO đa nguồn + duyệt admin

- **ID:** `20261017-1830-authentik-sso-pending-approve.md`
- **Từ:** Cursor Master (plan SSO pending-approve)
- **PROGRESS:** T-220 (Sources) → T-221 (smoke)
- **Ưu tiên:** P1
- **deploy:** no (app `vnstocks` không đổi)
- **merge_main:** yes (docs/blueprints đã trên main khi brief chạy)
- **infra:** yes
- **user_confirmed_infra:** yes
- **Scope infra:** chỉ `/opt/authentik` blueprints + `.env` Sources — **CẤM** nginx stream / sshd / UFW / `down -v`

---

## Mục tiêu

1. Nạp blueprint `atz-source-enrollment` + `atz-social-sources` vào `/opt/authentik/blueprints/`.
2. Human đã (hoặc sẽ) điền `AUTHENTIK_SOURCES_*` vào `/opt/authentik/.env`.
3. Enable Google/Facebook khi secret có; OIDC generic để sẵn (enable khi có issuer).
4. Smoke T-221: SSO → pending block → admin activate → `atz.vn` OK.

## Đọc trước

- `docs/infrastructure/AUTHENTIK_SOCIAL_SOURCES_BRIEF.md`
- `deploy/authentik/blueprints/atz-source-enrollment.yaml`
- `deploy/authentik/blueprints/atz-social-sources.yaml`
- `docs/adr/0006-no-oidc-client-in-streamlit.md`

## CẤM

1. nginx stream / SSH / firewall / sshd  
2. `docker compose down -v` Authentik hoặc xóa volume Postgres  
3. Commit `.env` / secret  
4. OIDC client / Authlib trong `vnstocks`  

## Done khi

1. Blueprint có trên VPS; flow `atz-source-enrollment` tồn tại  
2. Sources Google/FB hiện trên Federation (enabled chỉ khi env đủ)  
3. Outbox `…-1830-authentik-sso-pending-approve-DONE.md` (hoặc FAIL) + checklist smoke tick  
4. Cập nhật PROGRESS T-220/T-221 result  

## Smoke (T-221)

Theo acceptance trong brief SOCIAL_SOURCES — bắt buộc tick trong outbox.
