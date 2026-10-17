# SPEC: VANTIQ Account UX + Authentik (atz.vn)

**Cho:** VPSbot / Grok · **ADR:** `docs/adr/0003-account-ux-authentik-bff.md`  
**Host app:** `/opt/vnstocks` · **Host auth:** `/opt/authentik` · **SSH client:** Port **443** (nginx stream — **CẤM đụng**)

## Goal

Trang Tài khoản theme VANTIQ trên https://atz.vn. Không nhúng Authentik UI. Không gọi Authentik API từ browser.

## Current system (phải tôn trọng)

| Thành phần | Thực tế |
|------------|---------|
| Auth | Nginx **forward auth** `auth_request` → outpost; header `X-authentik-*` → Streamlit |
| App stack | `docker-compose.yml` tại `/opt/vnstocks`: `vnstocks`, ingestion, filter-runner, alert-dispatcher, position-monitor, index-feed, **redis** (`realtime` internal) |
| DB app | SQLite `data/signals.db` (volume) — **không** migrate/xóa |
| Auth stack | `/opt/authentik`: postgresql + server + worker; networks `internal` + external **`n8n_proxy-network`**; **không publish port** ra host |
| Nginx | Host proxy `atz.vn` / `auth.atz.vn`; SSH/ops qua **443 stream** (tách với HTTP site) |

## Non-goals / CẤM phá

- Clone full Authentik user dashboard
- Browser → Authentik CORS API
- **OIDC Client trong Streamlit** (Authlib / code flow / JWT session / `CLIENT_SECRET` trong app) — xem ADR **0006**; Social Login = Authentik Sources ([brief](../infrastructure/AUTHENTIK_SOCIAL_SOURCES_BRIEF.md))
- Đổi **sshd**, firewall, nginx **stream** / SSH reverse, cert/ACME trừ brief infra + `user_confirmed_infra: yes`
- Nối bừa network Docker: **không** gắn `vnstocks` vào Authentik `internal` (Postgres)
- Publish thêm port host; `docker network rm`; `down -v`; xóa volume redis/sqlite/authentik DB
- Broad reverse-proxy mọi path Authentik API
- Force push; commit `.env` / token

## Architecture (đã chốt + ý Gemini giữ)

**Phase 1 (mặc định — làm trước, không đụng Docker network cross-stack):**

```
Browser → atz.vn (nginx auth_request giữ nguyên)
       → Streamlit "Tài khoản": đọc identity từ header (hoặc st.context / proxy headers đã inject)
       → Deep link password/MFA → https://auth.atz.vn/... (flow đã brand nếu có)
       → Logout → 302 browser tới outpost/Authentik end-session → rd=https://atz.vn/ hoặc /huong-dan
```

- **Không** cần BFF gọi Authentik API trong Phase 1.
- **Không** join `n8n_proxy-network` từ compose vnstocks.

**Phase 2 (chỉ nếu Phase 1 xong + brief riêng + `user_confirmed_infra` nếu đụng nginx/network):**

- BFF hẹp `GET /api/account/me` enrich qua Authentik API **server-side**
- Cách an toàn: gọi `https://auth.atz.vn` (HTTPS công cộng) từ container **hoặc** join **chỉ** `n8n_proxy-network` (external) — **cấm** join `internal` Postgres
- Token API least-privilege qua env name `AUTHENTIK_API_TOKEN` — không commit

## Module A — Front-end Streamlit

- File gợi ý: `src/atz/ui/account_page.py` + gắn nav/pages hiện có
- Hiển thị: username, email, name, groups (từ header)
- Link: Đổi mật khẩu / TOTP → URL trong `config/*.yaml`
- Nút Đăng xuất → Module C
- Theme: `brand.py` + `theme_tokens.py` / `COLOR_TOKENS.md` — không theme mặc định AI

## Module B — BFF

- **Phase 1:** không bắt buộc. Helper thuần Python parse headers → dict `me`.
- **Phase 2:** FastAPI sidecar **cùng** compose vnstocks, **không** publish port ra host; chỉ reverse qua nginx location đã có auth_request — **chỉ khi brief Phase 2**.

## Module C — Logout (SLO)

1. Clear cache `st.session_state` liên quan user (nếu có)
2. Redirect browser tới `account.logout_url` (config) — phải hủy cookie outpost
3. Verify thủ công: mở lại atz.vn → bắt login

## Module D — Config

```yaml
# config/account.yaml (hoặc block trong yaml hiện có)
account:
  enabled: true
  logout_url: ""           # điền trên VPS sau khi xác nhận path Authentik 2026.8
  password_flow_url: ""
  mfa_flow_url: ""
  # Phase 2 only:
  # authentik_api_url: ""  # prefer https://auth.atz.vn — tránh nối sai network
```

Secrets: chỉ **tên** env trong docs; giá trị trên VPS.

## Module E — Docker / Nginx / Deploy safety checklist

Trước mọi lệnh VPS, xác nhận:

- [ ] Không sửa file nginx liên quan `stream {` / SSH / `rd.atz.vn` trừ brief + confirm
- [ ] Không `docker compose down -v` / xóa volume
- [ ] Không đổi network `realtime` (internal) của Redis
- [ ] Deploy app: `DOCKER_BUILDKIT=1 docker compose build vnstocks` && `up -d --no-deps vnstocks` tại `/opt/vnstocks`
- [ ] Stack Authentik `/opt/authentik`: **không restart** trừ khi brief Phase 2/E yêu cầu
- [ ] Sau deploy: `docker ps` — redis, vnstocks, authentik-server vẫn Up; SSH:443 vẫn vào được (self-check ngắn)

## Tests

- Unit: parse headers → me; thiếu username → coi chưa đăng nhập / 401 logic
- Manual: account page; logout buộc login lại
- Không gọi mạng Authentik trong CI Phase 1

## Done when

1. Trang Tài khoản VANTIQ trên atz.vn (Phase 1)
2. Logout hủy phiên Authentik/outpost
3. Không có request Authentik API từ browser (DevTools)
4. Network Docker / SSH:443 / Redis / SQLite nguyên vẹn
5. Outbox DONE: HEAD, lệnh chạy, checklist safety đã tick, rủi ro còn lại
