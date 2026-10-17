# Brief VPSbot — Account UX Phase 1 (an toàn hạ tầng)

- **ID:** `20261017-1106-account-ux-phase1.md`
- **Từ:** Cursor Orchestrator (kiến trúc sư)
- **Ưu tiên:** P1
- **deploy:** yes
- **merge_main:** yes
- **infra:** no
- **user_confirmed_infra:** no
- **Spec bắt buộc:** `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md`
- **ADR:** `docs/adr/0003-account-ux-authentik-bff.md`

---

## Mục tiêu

Phase 1 only: trang **Tài khoản** theme VANTIQ trên Streamlit; identity từ header Authentik forward-auth; logout = redirect browser hủy phiên outpost. **Không** BFF gọi Authentik API; **không** nối Docker network cross-stack.

## Phạm vi

- `src/atz/ui/account_page.py` (+ wire nav/pages)
- `config/*.yaml` block `account.*` (URL logout / password / mfa — có thể để trống + Notes cách điền trên VPS)
- Tests unit parse headers
- Deploy chỉ service `vnstocks` tại `/opt/vnstocks` (SSH:443)

## CẤM (phá hủy hạ tầng = FAIL ngay)

1. Sửa nginx **stream** / SSH / `rd.atz.vn` / firewall / sshd  
2. `docker compose down -v`, xóa volume redis / sqlite / authentik postgres  
3. Đổi network `realtime` (Redis internal) hoặc gắn `vnstocks` vào Authentik `internal`  
4. Join `n8n_proxy-network` trong Phase 1  
5. Restart stack `/opt/authentik` trừ khi brief khác  
6. Publish thêm port host; commit `.env` / token  
7. Gọi Authentik API từ browser hoặc nhúng Authentik UI  

## Ý Gemini / hội đồng giữ lại

- Phase 1 **headers-only** (giảm rủi ro network + token)
- Deep-link password/MFA sang `auth.atz.vn` (không clone UI bảo mật)
- SLO bằng **redirect browser**, không tự bịa curl xóa session phía server nếu chưa rõ API
- BFF/API enrich = **Phase 2 brief riêng** sau khi Phase 1 ổn

## Done khi

1. Code + test Pass; merge `main`  
2. Deploy `vnstocks`; checklist safety trong SPEC đã tick trong outbox  
3. Outbox `…-1106-account-ux-phase1-DONE.md` (hoặc FAIL): HEAD, lệnh, xác nhận SSH:443 + redis + authentik-server vẫn Up  
4. Không đụng file ngoài `/opt/vnstocks` repo app (không sửa `/opt/authentik` Phase 1)

## Tham chiếu đọc trước

- `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md`
- `deploy/authentik/nginx/atz.vn.conf` (hiểu forward auth — **không sửa** Phase 1)
- `docker-compose.yml` networks `realtime`
- `AGENTS.md`
