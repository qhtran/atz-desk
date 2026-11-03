# Optional ForwardAuth — DEV Desk Session / Welcome Gate
# Nếu Outpost session OK → inject X-authentik-*.
# Nếu 401 → @atz_soft_auth_continue (proxy không header; FastAPI dùng atz_desk_session).
# Include trong location /api/ và /ws/ (dev.atz.vn only). Không dùng trên atz.vn prod.

auth_request /outpost.goauthentik.io/auth/nginx;
error_page 401 = @atz_soft_auth_continue;
auth_request_set $auth_cookie $upstream_http_set_cookie;
add_header Set-Cookie $auth_cookie;
include /etc/nginx/snippets/security-headers.conf;

auth_request_set $authentik_username $upstream_http_x_authentik_username;
auth_request_set $authentik_groups $upstream_http_x_authentik_groups;
auth_request_set $authentik_email $upstream_http_x_authentik_email;
auth_request_set $authentik_name $upstream_http_x_authentik_name;
auth_request_set $authentik_uid $upstream_http_x_authentik_uid;

proxy_set_header X-authentik-username $authentik_username;
proxy_set_header X-authentik-groups $authentik_groups;
proxy_set_header X-authentik-email $authentik_email;
proxy_set_header X-authentik-name $authentik_name;
proxy_set_header X-authentik-uid $authentik_uid;
