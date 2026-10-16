# Brief VPSbot

- **ID:** `YYYYMMDD-HHMM-<topic>.md`
- **Từ:** Cursor Orchestrator / user
- **Ưu tiên:** P0 | P1 | P2
- **deploy:** yes | no
- **merge_main:** yes | no
- **infra:** no | docker | nginx | db | server | mixed
- **user_confirmed_infra:** yes | no  *(bắt buộc `yes` nếu nginx/SSH/firewall/Authentik)*

---

## Mục tiêu

(1–3 câu)

## Phạm vi

### App / code
- module / file: `…`

### Infra (nếu có)
- Docker / compose: `…`
- Nginx / proxy: `…`
- DB / Redis / volume: `…`
- Server setup: `…`

## Không đụng

- `…`

## Done khi

1. …
2. …

## Tham chiếu

- Auditor report (nếu có): `docs/auditorbot/…`
- Issue / chat: …

## Ghi chú VPS (SSH)

- Liên lạc server: **SSH** (VPSbot tự SSH; không nhờ Cursor)
- Host path: `/opt/vnstocks`
- Services restart: `vnstocks` / `ingestion` / …
