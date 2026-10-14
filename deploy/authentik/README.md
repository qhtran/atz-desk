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

2FA bằng TOTP là bắt buộc. User chưa có mã sẽ thấy mã QR ngay sau mật khẩu và phải quét trước khi vào `atz.vn`. Quét bằng ứng dụng Authenticator, rồi nhập 6 số.

Đăng ký: trên trang đăng nhập có liên kết đăng ký, hoặc mở `https://auth.atz.vn/if/flow/atz-enrollment/`. Tài khoản mới nằm ở nhóm `cho-duyet`, trạng thái chưa kích hoạt, nên chưa đăng nhập được. Sau khi gửi form, user thấy thông báo chờ duyệt và link `https://atz.vn/huong-dan`. Trang này không yêu cầu đăng nhập.

Phê duyệt: `https://auth.atz.vn/if/admin/` → Directory → Users. Lọc nhóm `cho-duyet`, mở user, bật **Active**, rồi Update. User đăng nhập lại, quét TOTP, rồi vào `https://atz.vn`.

Giao diện Authentik 2026.8.3 không có gói tiếng Việt. Form đăng ký dùng nhãn tiếng Việt. Các nút sẵn của Authentik vẫn là tiếng Anh.

## Gia hạn chứng chỉ auth.atz.vn

```sh
/opt/authentik/renew-auth-cert.sh
```

Certbot ghi chứng chỉ trên host. Hook HTTP-01 là `/opt/authentik/acme-auth.sh` và `acme-cleanup.sh`. Script copy bản thường vào volume `n8n_letsencrypt`, rồi kiểm tra và reload Nginx.
