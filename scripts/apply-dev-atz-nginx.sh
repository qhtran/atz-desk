#!/usr/bin/env bash
# Sync deploy/nginx_dev.conf + ForwardAuth snippet → nginx-reverse-proxy (dev.atz.vn).
# Chạy trên VPS (hoặc SSH từ laptop). ADR 0007: cần user_confirmed_infra trước khi apply.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${ROOT}/deploy/nginx_dev.conf"
SNIP="${ROOT}/deploy/nginx_forward_auth.inc"
SNIP_OPT="${ROOT}/deploy/nginx_forward_auth_optional.inc"
NGINX_C="${NGINX_CONTAINER:-nginx-reverse-proxy}"
TARGET="/etc/nginx/conf.d/dev.atz.vn.conf"
SNIP_TARGET="/etc/nginx/snippets/atz_forward_auth.inc"
SNIP_OPT_TARGET="/etc/nginx/snippets/atz_forward_auth_optional.inc"

if [[ ! -f "$CONF" ]]; then
  echo "missing $CONF" >&2
  exit 1
fi
if [[ ! -f "$SNIP" ]]; then
  echo "missing $SNIP" >&2
  exit 1
fi
if [[ ! -f "$SNIP_OPT" ]]; then
  echo "missing $SNIP_OPT" >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$NGINX_C"; then
  echo "container $NGINX_C not running" >&2
  exit 1
fi

docker cp "$SNIP" "${NGINX_C}:${SNIP_TARGET}"
docker cp "$SNIP_OPT" "${NGINX_C}:${SNIP_OPT_TARGET}"
docker cp "$CONF" "${NGINX_C}:${TARGET}"
docker exec "$NGINX_C" nginx -t
docker exec "$NGINX_C" nginx -s reload
echo "==> nginx ForwardAuth snippet → ${SNIP_TARGET}"
echo "==> nginx ForwardAuth optional → ${SNIP_OPT_TARGET}"
echo "==> nginx dev.atz.vn synced ($(grep -m1 'desk-api' "$CONF" || true))"
