#!/usr/bin/env bash
# Sync deploy/nginx_dev.conf → nginx-reverse-proxy volume (dev.atz.vn upstream).
# Chạy trên VPS (hoặc SSH từ laptop: ATZ_VPS_SSH + script này remote).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${ROOT}/deploy/nginx_dev.conf"
NGINX_C="${NGINX_CONTAINER:-nginx-reverse-proxy}"
TARGET="/etc/nginx/conf.d/dev.atz.vn.conf"

if [[ ! -f "$CONF" ]]; then
  echo "missing $CONF" >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$NGINX_C"; then
  echo "container $NGINX_C not running" >&2
  exit 1
fi
docker cp "$CONF" "${NGINX_C}:${TARGET}"
docker exec "$NGINX_C" nginx -t
docker exec "$NGINX_C" nginx -s reload
echo "==> nginx dev.atz.vn synced ($(grep -m1 'desk-api' "$CONF" || true))"
