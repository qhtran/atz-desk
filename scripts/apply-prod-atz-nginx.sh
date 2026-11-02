#!/usr/bin/env bash
# Sync deploy/nginx_prod_atz.conf → nginx-reverse-proxy (/etc/nginx/conf.d/atz.vn.conf).
# ADR 0007: cần user_confirmed_infra: yes. Chạy NGOÀI giờ giao dịch.
# Mặc định REFUSE trừ khi ATZ_APPLY_PROD_NGINX=1.
#
# Usage (trên VPS, cwd repo Desk — thường /opt/atz-desk):
#   ATZ_APPLY_PROD_NGINX=1 ./scripts/apply-prod-atz-nginx.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${ROOT}/deploy/nginx_prod_atz.conf"
SNIP="${ROOT}/deploy/nginx_forward_auth.inc"
NGINX_C="${NGINX_CONTAINER:-nginx-reverse-proxy}"
TARGET="/etc/nginx/conf.d/atz.vn.conf"
SNIP_TARGET="/etc/nginx/snippets/atz_forward_auth.inc"
BACKUP_DIR="${ROOT}/deploy/.nginx-backup"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/atz.vn.conf.${TS}.bak"

if [[ "${ATZ_APPLY_PROD_NGINX:-0}" != "1" ]]; then
  echo "REFUSE: set ATZ_APPLY_PROD_NGINX=1 (và user_confirmed_infra: yes) trước khi apply atz.vn nginx." >&2
  echo "Conf sẵn: $CONF" >&2
  exit 2
fi

if [[ ! -f "$CONF" ]]; then
  echo "ERR: missing $CONF" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$NGINX_C"; then
  echo "ERR: container $NGINX_C not running" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "==> conf.d hiện có trong ${NGINX_C}:"
docker exec "$NGINX_C" ls -la /etc/nginx/conf.d/ || true

# Backup nếu đã có file đích
if docker exec "$NGINX_C" test -f "$TARGET"; then
  echo "==> backup ${TARGET} → ${BACKUP_FILE}"
  docker cp "${NGINX_C}:${TARGET}" "$BACKUP_FILE"
else
  echo "==> chưa có ${TARGET} trong container (sẽ tạo mới)"
fi

if [[ -f "$SNIP" ]]; then
  echo "==> sync ForwardAuth snippet → ${SNIP_TARGET}"
  docker cp "$SNIP" "${NGINX_C}:${SNIP_TARGET}"
fi

echo "==> docker cp nginx_prod_atz.conf → ${NGINX_C}:${TARGET}"
docker cp "$CONF" "${NGINX_C}:${TARGET}"

echo "==> nginx -t"
if ! docker exec "$NGINX_C" nginx -t; then
  echo "ERR: nginx -t FAILED — rollback" >&2
  if [[ -f "$BACKUP_FILE" ]]; then
    docker cp "$BACKUP_FILE" "${NGINX_C}:${TARGET}"
    echo "==> restored ${TARGET} from ${BACKUP_FILE}" >&2
    docker exec "$NGINX_C" nginx -t >&2 || echo "WARN: nginx -t vẫn fail sau restore — kiểm tra tay" >&2
  else
    echo "==> không có backup — xóa file mới để tránh conf hỏng" >&2
    docker exec "$NGINX_C" rm -f "$TARGET" || true
  fi
  exit 1
fi

echo "==> nginx -s reload"
docker exec "$NGINX_C" nginx -s reload
echo "==> OK: atz.vn nginx applied (${TARGET})"
echo "    Verify: curl -sI https://atz.vn/ | head"
echo "    Rollback thủ công: docker cp ${BACKUP_FILE:-<bak>} ${NGINX_C}:${TARGET} && docker exec ${NGINX_C} nginx -t && docker exec ${NGINX_C} nginx -s reload"
