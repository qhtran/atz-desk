# Snippet: Authentik ForwardAuth — include bên trong location { } (/, /api/, /ws/)
# VPS path trong container nginx-reverse-proxy:
#   /etc/nginx/snippets/atz_forward_auth.inc
# Sync: scripts/apply-dev-atz-nginx.sh (docker cp + nginx -t + reload)
#
# Yêu cầu sẵn có:
#   location /outpost.goauthentik.io { proxy_pass http://authentik-server:9000/... }
#   location @goauthentik_proxy_signin { ... }
#
# Header → FastAPI (backend/identity.py): X-authentik-username|email|name|uid|groups

auth_request /outpost.goauthentik.io/auth/nginx;
error_page 401 = @goauthentik_proxy_signin;
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
