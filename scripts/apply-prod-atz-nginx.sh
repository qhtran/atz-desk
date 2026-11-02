#!/usr/bin/env bash
# Sync deploy/nginx_prod_atz.conf → nginx-reverse-proxy (atz.vn).
# ADR 0007: yêu cầu user_confirmed_infra: yes trước khi chạy.
# Mặc định REFUSE trừ khi ATZ_APPLY_PROD_NGINX=1.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${ROOT}/deploy/nginx_prod_atz.conf"
SNIP="${ROOT}/deploy/nginx_forward_auth.inc"
NGINX_C="${NGINX_CONTAINER:-nginx-reverse-proxy}"
TARGET="/etc/nginx/conf.d/atz.vn.conf"
SNIP_TARGET="/etc/nginx/snippets/atz_forward_auth.inc"

if [[ "${ATZ_APPLY_PROD_NGINX:-0}" != "1" ]]; then
  echo "REFUSE: set ATZ_APPLY_PROD_NGINX=1 and user_confirmed_infra: yes before applying atz.vn nginx." >&2
  echo "Draft conf ready at: $CONF" >&2
  exit 2
fi
if [[ ! -f "$CONF" ]]; then
  echo "missing $CONF" >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$NGINX_C"; then
  echo "container $NGINX_C not running" >&2
  exit 1
fi
if [[ -f "$SNIP" ]]; then
  docker cp "$SNIP" "${NGINX_C}:${SNIP_TARGET}"
fi
docker cp "$CONF" "${NGINX_C}:${TARGET}"
docker exec "$NGINX_C" nginx -t
docker exec "$NGINX_C" nginx -s reload
echo "==> nginx atz.vn synced (DRAFT apply complete)"
