# Task T-p3-p4-cutover-close — P3 Risk parity verify + P4 tắt Streamlit UI

**Owner:** ag2  
**Status:** Done (2026-11-03)  
**Phụ thuộc:** `T-desk-prod-cutover-activate` (atz.vn → Desk SPA)

## Mục tiêu

Đóng ADR 0009 cutover: xác nhận P3 data/risk parity (không bịa số spreadsheet), tắt UI Streamlit `:8501`, cập nhật bus.

## P3 — Risk YAML & Portfolio parity (1a: verify only)

| Hạng mục | Kết quả 2026-11-03 |
|----------|-------------------|
| `config/trading_station.yaml` `scoring_thresholds` | Có số (weights / RSI / MA) |
| `position_sizing` + `risk_tolerance.profiles` | **Còn `null` có chủ đích** — chờ spreadsheet Hiến; không invent |
| `config/advisor_score.yaml` | Có số (song song scoring) |
| Prod volume `atz_prod_data` (`docker-compose.prod-desk.yml`) | Pass — `portfolio.db` / `prod_trading.db` trên volume riêng |
| Desk-dev data | Tách — bind `./data` + `dev_trading.db`, không dùng `atz_prod_data` |

**Todo còn lại (không block cutover UI):** Hiến điền SL/TP/`default_equity_pct`/`user_profiles`.

## P4 — Decommission Streamlit UI (2a)

- Script: `scripts/decommission-streamlit-ui.sh` (`ATZ_DECOMMISSION_STREAMLIT_UI=1`)
- Chỉ stop/rm container **`vnstocks`** (`:8501`)
- **Không** đụng: `nginx-reverse-proxy`, Authentik, `atz-desk-*`, bot `atz-ingestion` / filter / alert / position / index / ssi-stream
- Compose: `vnstocks` → `profiles: ["legacy-ui"]` (không tự `up` lại)
- Nginx draft: `deploy/nginx_prod_atz.conf` ghi chú không còn upstream `:8501` (live `atz.vn.conf` đã Desk từ activate)

Rollback UI khẩn:

```bash
cd /opt/vnstocks && docker compose --profile legacy-ui up -d vnstocks
```

## Ngoài phạm vi

- Bịa số risk từ spreadsheet
- Stop bot Streamlit-era (ingestion/…)
- Xóa volume/data SQLite legacy

## Done khi

- [x] P3 verify ghi vào packet này
- [x] Script P4 trong repo
- [x] Compose profile + nginx draft note
- [x] VPS: container `vnstocks` không running
- [x] NOW.md cập nhật mốc P3/P4
