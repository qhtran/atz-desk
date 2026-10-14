# Authentik cho atz.vn

Authentik 2026.8.3 chặn `https://atz.vn` và `https://www.atz.vn`. Trang quản trị là `https://auth.atz.vn`. `n8n.tiengvang.net` và SSH qua `rd.atz.vn` không đi qua Authentik.

Bản 2026.8 lưu phiên và hàng đợi trong PostgreSQL. Không chạy Redis.

## File trên VPS

- `/opt/authentik/docker-compose.yml`
- `/opt/authentik/.env` mode 600, không commit
- Mật khẩu `akadmin`: `/opt/authentik/secrets/akadmin.password` mode 600

```sh
cd /opt/authentik && docker compose up -d
```

## Admin

Mở `https://auth.atz.vn/if/admin/`. User là `akadmin`. Xem mật khẩu:

```sh
ssh -i ~/.ssh/id_ed25519 -o IdentitiesOnly=yes root@112.213.88.230 cat /opt/authentik/secrets/akadmin.password
```

Thêm user: Directory → Users → Create. Gán nhóm nếu user đó được vào app.

2FA: user tự thêm tại `https://auth.atz.vn/if/user/#/settings` mục MFA devices, chọn TOTP. Authentik chỉ hỏi mã sau khi thiết bị đã được thêm. Chưa bật bắt buộc cho mọi user, vì bật trước khi quét mã sẽ khóa đăng nhập.

## Gia hạn chứng chỉ auth.atz.vn

```sh
/opt/authentik/renew-auth-cert.sh
```

Certbot ghi chứng chỉ trên host. Hook HTTP-01 là `/opt/authentik/acme-auth.sh` và `acme-cleanup.sh`. Script copy bản thường vào volume `n8n_letsencrypt`, rồi kiểm tra và reload Nginx.
