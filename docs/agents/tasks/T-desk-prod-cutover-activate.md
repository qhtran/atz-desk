# Task T-desk-prod-cutover-activate — Kích hoạt atz.vn Desk (ngoài giờ GD)

**Owner:** human (VPS) + ag2 (repo/script)  
**Status:** Done (VPS 2026-11-03) — desk `:8001` + nginx `atz.vn.conf` applied; backup `deploy/.nginx-backup/atz.vn.conf.20261103-012208.bak`  
**Phụ thuộc:** `T-desk-prod-cutover-p0` prep đã trên `main`

## Mục tiêu

Đưa container prod-desk lên `:8001`, rồi (khi đủ gate) apply `deploy/nginx_prod_atz.conf` vào `nginx-reverse-proxy`.

## Gate trước apply nginx

- [ ] `user_confirmed_infra: yes`
- [ ] Ngoài giờ giao dịch VN
- [ ] `./scripts/deploy-prod-desk.sh` → healthz `:8001` Pass
- [ ] Biết rollback: backup trong `deploy/.nginx-backup/` (script tạo khi apply)

## Runbook VPS (`cd /opt/atz-desk`)

```bash
./scripts/deploy-prod-desk.sh
ATZ_APPLY_PROD_NGINX=1 ./scripts/apply-prod-atz-nginx.sh
```

Tuỳ chọn SSI writer:

```bash
docker compose -f docker-compose.prod-desk.yml --profile live up -d ssi-worker
```

## Ngoài phạm vi

- Agent không SSH apply giúp trừ khi human yêu cầu rõ sau gate
- Tắt Streamlit (P4) — sau verify ổn định
