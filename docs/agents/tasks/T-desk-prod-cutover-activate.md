# Task T-desk-prod-cutover-activate — Kích hoạt atz.vn Desk (ngoài giờ GD)

**Owner:** human (VPS) + ag2 (repo/script)  
**Status:** Doing — chờ chạy tay trên VPS  
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
