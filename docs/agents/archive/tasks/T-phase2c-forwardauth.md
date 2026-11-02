# Task T-phase2c-forwardauth — Phase 2C Authentik ForwardAuth

**Owner:** ag2  
**Status:** Done  
**Phạm vi:** `deploy/nginx_*.conf|inc`, `scripts/apply-dev-atz-nginx.sh`, `scripts/deploy-vps.sh`

## Mục tiêu

Chuẩn hóa ForwardAuth snippet + site `dev.atz.vn`; human apply lên `nginx-reverse-proxy` (không sites-available).

## File được sửa

- `deploy/nginx_forward_auth.inc` — auth_request + X-authentik-* headers (active)
- `deploy/nginx_dev.conf` — include snippet cho `/`, `/api/`, `/ws/`
- `scripts/apply-dev-atz-nginx.sh` — docker cp snippet + conf + nginx -t + reload
- `scripts/deploy-vps.sh` — sync snippet khi deploy-dev
- `docs/agents/NOW.md`

## DoD

- [x] Snippet active (không còn comment-only)
- [x] `/` `/api/` `/ws/` include ForwardAuth; `/healthz` + outpost bypass
- [x] Human: `user_confirmed_infra: yes` → chạy apply trên VPS
- [x] Verify: unauth → 302 Authentik; logged-in SPA + WS xanh; API nhận X-authentik-*

## Ngoài phạm vi

- Bật ForwardAuth trên compose local `:8080`
- Đụng stream.d / SSH / firewall
- Force push

## Báo

Cập nhật Last executor trên NOW sau khi human apply xong.
