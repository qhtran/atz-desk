# 20261017-1106-account-ux-phase1 — DONE

- **Status:** DONE
- **Brief:** `docs/bots/vpsbot/inbox/20261017-1106-account-ux-phase1.md`
- **HEAD (code):** `6d9afaa` feat(account): add VANTIQ account page from Authentik forward-auth headers
- **Branch:** `main` (merge_main: yes, commit thẳng lên main, không force push)
- **Deploy:** yes, chỉ service `vnstocks` tại `/opt/vnstocks` (04:14–04:15 UTC)

## Summary

Phase 1 headers-only. Thêm nav **Tài khoản** (segmented control trong `ui/pages.py`, ẩn nếu `account.enabled: false`). Trang hiện thẻ hồ sơ theme VANTIQ (`brand.py` + `theme_tokens.py`): tên, `@username`, email, chip groups, lấy từ header `X-authentik-*` mà nginx forward-auth đã gắn. Nút **Đổi mật khẩu** và **Cài xác thực 2 lớp (TOTP)** là deep-link sang flow trên `auth.atz.vn` (tab mới). **Đăng xuất** là link cùng tab (`target="_self"`) tới `https://atz.vn/outpost.goauthentik.io/sign_out`: outpost xóa cookie rồi chạy invalidation flow của provider (`default-provider-invalidation-flow` theo blueprint `atz-forward-auth.yaml`). Điều hướng cả trang kết thúc phiên websocket Streamlit nên `st.session_state` cũ bị bỏ theo. Không gọi Authentik API (cả browser lẫn server), không BFF, không đụng network Docker.

An toàn: mọi giá trị header được `html.escape` trước khi chèn HTML; URL trong config chỉ nhận `https://` có host (chặn `javascript:`/`http:`), URL rỗng thì ẩn nút.

## Files

- `src/atz/engine/identity.py`: thêm `me_from_headers()` (thuần Python, không mạng) và `current_me()`. Không username thì trả `None` (= chưa đăng nhập). Groups tách theo `|`.
- `src/atz/ui/account_page.py` (mới): `load_account_config`, `safe_url`, `profile_card_html`, `logout_link_html`, `show_account`.
- `src/atz/ui/pages.py`: wire nav "Tài khoản".
- `config/account.yaml` (mới): block `account.*` (enabled, logout_url, password_flow_url, mfa_flow_url). Chỉ URL công khai, không secret.
- `tests/test_account.py` (mới): 9 test.

URL đã điền sẵn (probe GET read-only từ VPS, không cookie):

| Key | URL | Kết quả probe |
|-----|-----|---------------|
| logout_url | `https://atz.vn/outpost.goauthentik.io/sign_out` | 302 → `/outpost.goauthentik.io/start?rd=https://atz.vn` |
| password_flow_url | `https://auth.atz.vn/if/flow/default-password-change/` | 200 |
| mfa_flow_url | `https://auth.atz.vn/if/flow/default-authenticator-totp-setup/` | 200 (slug khớp blueprint `atz-enrollment.yaml`) |

Đổi URL: sửa `config/account.yaml` rồi build lại `vnstocks` (config được COPY vào image).

## Tests

- `tests/test_account.py` + `tests/test_identity.py`: **11 passed** (parse header đủ/thiếu/hoa-thường, thiếu username = chưa đăng nhập, safe_url, config load/thiếu file, config repo hợp lệ, escape XSS trong thẻ hồ sơ, logout link cùng tab + chặn URL xấu).
- Streamlit `AppTest` render `show_account` với header giả: không exception, có thẻ hồ sơ + link đăng xuất.
- `import ui.pages` OK.
- Full suite: **200 passed, 1 skipped, 3 failed**. 3 lỗi có sẵn từ trước, không liên quan brief: `test_filter_runner::test_integration_real_ingestion_stream`, `test_ingestion::test_t1_real_kbs_batch_normalized_and_cached` (mạng), `test_ui_realtime::test_t1_refresh_interval_trading_hours`.

## Commands (rút gọn)

```
cd /opt/vnstocks && git pull --ff-only origin main
docker run --rm --network vnstocks_realtime -v /opt/vnstocks:/src:ro --tmpfs /src/data -w /src -e PYTHONPATH=/src/src/atz vnstocks-vnstocks python -m pytest -q tests
git commit (6d9afaa) && git push origin main
DOCKER_BUILDKIT=1 docker compose build vnstocks
docker compose up -d --no-deps vnstocks
```

## Safety checklist (SPEC Module E)

- [x] Không sửa nginx (`stream {` / SSH / `rd.atz.vn` / `deploy/authentik/nginx/atz.vn.conf`), sshd, firewall
- [x] Không `docker compose down -v` / không xóa volume (redis_data, data/signals.db 184320 bytes vẫn nguyên)
- [x] Không đổi network `realtime`; `vnstocks` vẫn chỉ ở `vnstocks_default` + `vnstocks_realtime` (không join Authentik `internal`, không join `n8n_proxy-network`)
- [x] Deploy đúng `docker compose build vnstocks` + `up -d --no-deps vnstocks` tại `/opt/vnstocks`
- [x] Không restart / không sửa `/opt/authentik`
- [x] Không publish thêm port (vẫn `127.0.0.1:8501`); không commit `.env` / token
- [x] Sau deploy: `vnstocks` Up, `/_stcore/health` = ok, `atz-redis` healthy (PING → PONG), `authentik-server` Up 2 days (healthy), `nginx-reverse-proxy` Up, `https://atz.vn/` → 302 (forward auth vẫn chặn), SSH:443 vào lại được ngay sau deploy

## Notes / rủi ro còn lại

1. **Cần kiểm tra tay (user):** mở atz.vn → Tài khoản → Đăng xuất → mở lại atz.vn phải bắt đăng nhập. Bot không có phiên Authentik nên chỉ xác nhận được đường `sign_out` trả 302 về flow đăng nhập. Nếu sau sign_out vẫn còn phiên Authentik (chỉ mất cookie outpost), cần kiểm tra provider `invalidation_flow` (brief riêng, có thể đụng Authentik).
2. Kiểm tra DevTools: trang không có request nào tới Authentik API; chỉ các link điều hướng.
3. Flow URL trả 200 vì là SPA, nên 200 chưa chứng minh flow chạy đúng; cần bấm thử khi đã đăng nhập.
4. Thanh bên vẫn còn nút cũ "Tài khoản" trỏ `https://auth.atz.vn/if/user/` (ngoài phạm vi brief, không sửa). Orchestrator quyết định có bỏ/đổi sang trang mới không.
5. Không có header (chạy local) thì trang báo "Chưa đăng nhập" và ẩn nút đăng xuất.
