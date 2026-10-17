# Prompt dán VPSbot — Account UX Phase 1

Copy khối dưới (đã tính atz.vn: VPS, Docker, nginx forward-auth, Redis, SQLite, SSH:443).

---

```
Bạn là VPSbot. Làm đúng brief:
  docs/bots/vpsbot/inbox/20261017-1106-account-ux-phase1.md
Đọc full spec:
  docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md
và PROTOCOL.md. git pull --ff-only origin main trước.

Hạ tầng hiện tại (KHÔNG phá):
- App: /opt/vnstocks — compose có redis network "realtime" (internal), SQLite data/signals.db
- Auth: /opt/authentik — tách stack, network internal + n8n_proxy-network; không publish port
- Nginx host: forward auth atz.vn; SSH ops qua Port 443 stream — CẤM sửa stream/sshd/firewall
- Liên lạc VPS: SSH Port 443

Phase 1 ONLY:
- Trang Tài khoản Streamlit theme VANTIQ; identity từ X-authentik-* headers
- Logout = redirect browser tới account.logout_url (hủy outpost session)
- Deep link password/MFA — không clone Authentik UI
- KHÔNG Authentik API từ browser; KHÔNG BFF Phase 2; KHÔNG join n8n_proxy-network
- KHÔNG down -v / xóa volume / restart authentik / đổi redis network

Deploy: chỉ build + up -d --no-deps vnstocks. Self-check: docker ps redis+vnstocks+authentik-server Up; SSH còn vào được.

Test module Pass. Commit+push+merge main theo brief. Outbox:
  docs/bots/vpsbot/outbox/20261017-1106-account-ux-phase1-DONE.md
kèm checklist safety đã tick. Rồi tiếp poll inbox khác.
```
