# Task T-step5-fe-api-ws-sync — Bước 5: Đồng bộ UI Frontend với Backend

**Owner:** ag2  
**Status:** Done  
**Phạm vi:** dev.atz.vn

## Mục tiêu

SPA dùng REST `/api/` + WS `/ws/` relative; parse `POST /api/iboard/daily-signals` khớp output vectorized; smoke nginx edge `:8080`.

## File được sửa

- `docs/agents/NOW.md`
- `frontend/index.html` (chỉ nếu endpoint/parse chưa khớp)
- `frontend/trading.html` (chỉ nếu hardcode domain/port)
- `frontend/debug-overlay.js` (chỉ nếu hardcode)
- `tests/test_daily_signals.py` (chỉ nếu thiếu assert contract hits)

## DoD

- [x] Fetch REST relative `/api/…` (không hardcode host/port)
- [x] WebSocket `ws(s)://` + host hiện tại + `/ws/priceboard`
- [x] Parse `ok/symbols/hits/filters/matched/scanned` render không vỡ
- [x] `docker compose -f docker-compose.dev.yml --profile edge up --build -d` → `http://127.0.0.1:8080` SPA + API + WS

## Ngoài phạm vi

- Prod Streamlit, Authentik/SSH/firewall, merge PR, F3 plan.md
- Force push / in secret

## Báo

Cập nhật 5 dòng Last executor trên `docs/agents/NOW.md`.
