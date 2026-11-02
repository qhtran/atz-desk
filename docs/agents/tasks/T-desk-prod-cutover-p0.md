# Task T-desk-prod-cutover-p0 — Gate Dual Stack atz.vn (ADR 0009)

**Owner:** ag2 / human  
**Status:** Doing (repo prep) — **chưa** apply nginx / chưa cutover live  
**Phạm vi:** `docker-compose.prod-desk.yml`, `.env.prod-desk.example`, `deploy/nginx_prod_atz.conf`, `scripts/deploy-prod-desk.sh`, `scripts/apply-prod-atz-nginx.sh`

## Mục tiêu

Chuẩn bị stack Desk prod song song `dev.atz.vn` theo ADR 0009. Không đụng nginx live cho đến `user_confirmed_infra: yes`.

## Parity checklist (Streamlit → Desk SPA)

- [ ] Real-time priceboard WebSocket + Redis ổn định trên desk-dev
- [ ] Authentik ForwardAuth → `X-authentik-*` vào FastAPI (`/api/account/me`)
- [ ] Risk YAML / Advisor Score đã điền số Hiến (`config/trading_station.yaml`)
- [ ] SQLite / volume prod ≠ dev (`atz_prod_data` vs data desk-dev)
- [ ] **SSI:** một writer prod (`--profile live`); desk-dev mock/tắt giờ vàng

## Human confirmation

```text
user_confirmed_infra: pending
```

Chỉ khi Pass checklist + `user_confirmed_infra: yes` mới được:

```bash
ATZ_APPLY_PROD_NGINX=1 ./scripts/apply-prod-atz-nginx.sh
```

## Ngoài phạm vi

- Apply nginx VPS trong task này
- Tắt Streamlit (P4) trước parity Pass
- Option B realtime quant streaming
