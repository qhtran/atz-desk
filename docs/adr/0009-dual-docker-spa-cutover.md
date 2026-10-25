# ADR 0009 — Dual Docker, cùng repo: cutover SPA thay Streamlit trên atz.vn

- **Status:** Accepted (2026-10-25, owner)
- **Context:** Prod `atz.vn` chạy Streamlit (`src/atz`) — MVP nhanh nhưng **realtime chậm** khi triển khai. `dev.atz.vn` chạy stack priceboard (**FastAPI + SPA + ssi-worker + Redis**) trong Docker **riêng** (`docker-compose.dev.yml`, project `atz_priceboard`). Authentik **dùng chung** prod/dev (ForwardAuth, cookie domain `atz.vn`). Sau khi port đủ tính năng từ Streamlit, owner thay **source trong Docker prod** bằng cùng loại stack dev — **nginx không đổi** (vẫn route domain → upstream container tương ứng).

## Quyết định

1. **Hai stack Docker độc lập, một codebase Git**
   - **DEV:** `dev.atz.vn` → compose dev (phát triển, debug, tính năng mới).
   - **PROD:** `atz.vn` → compose prod (khách); sau cutover chạy **cùng kiến trúc app** với dev (không còn Streamlit làm UI chính).
   - **Không** gộp hai môi trường vào một container; **không** bắt buộc đổi cấu hình nginx khi cutover — chỉ thay **image / build context / lệnh service** trong compose prod.

2. **Luồng promote code**
   - Feature/fix trên dev → verify trên **Docker dev** → `git push` → trên VPS prod: **`git pull` + rebuild/restart** stack prod (script kiểu `scripts/deploy-vps.sh dev` rồi `prod`).
   - Prod **không** tự nhận code chưa qua kiểm tra dev (quy trình owner, không auto-sync container-to-container).

3. **Cutover một lần (Streamlit → SPA trên prod Docker)**
   - Dừng / gỡ service Streamlit trong compose prod khi parity checklist Pass (spec riêng từng cụm tính năng).
   - Bật service priceboard (api, ssi-worker, redis priceboard hoặc tách redis theo ADR 0005) với **cùng repo** đã validate trên dev.
   - Migrate dữ liệu user (SQLite positions, sổ vốn) **một lần** nếu khách đã có dữ liệu trên Streamlit — không yêu cầu gộp DB dev ↔ prod.

4. **Dữ liệu & Redis**
   - **DB / volume prod ≠ dev** (dev được reset/thử; prod là nguồn chân lý khách). Cùng **username Authentik**, khác file DB / Redis instance theo môi trường (ADR 0005).
   - Priceboard worker prod **không** ghi `idx:quote:*` nếu vẫn có writer legacy — giữ quy ước hiện tại trong `backend/ssi_live.py`; thống nhất nguồn tick theo phase cutover.

5. **Legacy Streamlit**
   - Sau cutover: **không deploy** UI Streamlit trên `atz.vn`. Code `src/atz` UI có thể archive/xóa dần; logic Python tái sử dụng (**analysis/**, **datasource/**, filter, F3…) port sang **`backend/`** API, không duplicate lâu dài trên Streamlit.

6. **Infra gate**
   - Thay đổi compose prod / tắt Streamlit prod: tuân **ADR 0007** (`user_confirmed_infra: yes`) khi task ops chạm production.

## Hệ quả

- `dev.atz.vn` luôn tồn tại làm staging; `atz.vn` nhận bản promote ổn định.
- Cursor phạm vi active dev vẫn ưu tiên `backend/`, `frontend/`, compose dev — nhưng thiết kế API/UI hướng tới **một sản phẩm** thay Streamlit prod.
- Deploy script: mở rộng / duy trì target **`prod`** cùng pattern với **`dev`** (pull, build, healthz), không sửa nginx trong script mặc định.

## References

- `docs/architecture.md` (§ priceboard dev)
- `docs/adr/0005-data-placement-sqlite-redis.md`
- `docs/adr/0003-account-ux-authentik-bff.md`, `0006-no-oidc-client-in-streamlit.md`
- `docs/specs/PORTFOLIO_DEV_FROM_PROD.md`
- `scripts/deploy-vps.sh`, `docker-compose.dev.yml`
