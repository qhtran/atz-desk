# Authelia cho atz.vn

Trang đăng nhập là `https://auth.atz.vn`. `atz.vn` và `www.atz.vn` yêu cầu mật khẩu rồi TOTP. `n8n.tiengvang.net` không đi qua Authelia.

Nginx trong container `nginx-reverse-proxy` nghe HTTPS ở cổng 8443. Cổng 443 của máy chủ là `ssl_preread` và không sửa trong thư mục này.

## File trên VPS

- `/opt/authelia/docker-compose.yml`
- `/opt/authelia/config/configuration.yml`
- `/opt/authelia/config/users_database.yml` (không commit)
- `/opt/authelia/secrets/` mode 600 (không commit)

Mật khẩu admin ban đầu nằm ở `/opt/authelia/secrets/admin.password`. Lần đăng nhập đầu mở `https://auth.atz.vn`, nhập user `admin` và mật khẩu đó, rồi quét mã TOTP. Issuer trong ứng dụng xác thực là `atz.vn`.

Redis và Authelia chỉ nối vào mạng Docker `n8n_proxy-network`, không publish cổng.

## Thêm user

Trên VPS:

```sh
umask 077
openssl rand -base64 18 | tr -d '\n' > /opt/authelia/secrets/ten-user.password
docker run --rm -v /opt/authelia/secrets:/secrets:ro authelia/authelia:4.38.19 \
  authelia crypto hash generate argon2 --password "$(cat /secrets/ten-user.password)"
```

Chép dòng Digest vào `password` của user mới trong `/opt/authelia/config/users_database.yml`. File đang được theo dõi (`watch: true`). Giữ quyền file là user chạy container Authelia.

## Gia hạn chứng chỉ

```sh
/opt/authelia/renew-auth-cert.sh
```

Certbot ghi chứng chỉ trên host. Script copy bản thường (không phải symlink) vào volume `n8n_letsencrypt`, rồi kiểm tra và reload Nginx.
