# Task T-admin-control-panel-b3 — Admin Control Panel & Hot-reload Runtime Config

**Owner:** CDP / ag2  
**Status:** ARCHIVED / DONE — master_ack 2026-11-03  
**Phụ thuộc:** B1+B2 SPA auth/RBAC/Alerts (`cursor/unified-spa-rbac-baf6` @ `6733f7c`)  
**Ship:** PR #15 · `cursor/admin-control-panel-baf6` → `main` @ `930b8e8` · deploy `dev-local`

## Mục tiêu

Admin chỉnh ngưỡng stream alerts (RSI/MA/volume/cooldown) và risk placeholders trên SPA, không SSH/VPS; API có `is_admin` guard; hot-reload `QuantStreamListener`.

## DoD

- [x] `GET/PUT /api/admin/control-plane` + whitelist sanitize
- [x] Guard 401/403/`is_admin` (Authentik groups / `config/account.yaml` `admin_groups`)
- [x] Overlay `data/admin_runtime_config.json` (không ghi đè YAML image)
- [x] `QuantStreamListener.apply_config` (log `STREAM-CFG`)
- [x] Tab Admin SPA form tải/lưu
- [x] Tests `tests/test_admin_control_plane.py` Pass
- [x] Smoke deploy: 401/403/200 · PUT oversold 27 · GET overlay · WS alerts hello

## Phạm vi file

- `backend/admin_config_store.py`
- `backend/main.py`, `backend/engine/stream_listener.py`
- `frontend/index.html` (panel admin)
- `tests/test_admin_control_plane.py`

## Ngoài phạm vi

- Promote prod `:8001` (chỉ sau brief riêng)
- Sửa nginx / Authentik groups trên IdP
- Điền đầy đủ spreadsheet Risk YAML (vẫn Todo Hiến trên NOW)
