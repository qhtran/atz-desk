#!/usr/bin/env bash
# P4 — Tắt UI Streamlit legacy (`vnstocks` :8501). Không đụng nginx / Authentik / desk / bot.
# ADR 0009 § Legacy Streamlit. ADR 0007: cần xác nhận infra trước khi chạy trên VPS.
#
# Usage (VPS /opt/vnstocks hoặc Mac với Docker):
#   ATZ_DECOMMISSION_STREAMLIT_UI=1 ./scripts/decommission-streamlit-ui.sh
#
# An toàn mặc định: REFUSE trừ khi ATZ_DECOMMISSION_STREAMLIT_UI=1.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${ATZ_DECOMMISSION_STREAMLIT_UI:-}" != "1" ]]; then
  echo "REFUSE: set ATZ_DECOMMISSION_STREAMLIT_UI=1 để tắt container UI vnstocks (:8501)." >&2
  echo "Không đụng: nginx-reverse-proxy, authentik, atz-desk-*, bot ingestion/filter/alert/…" >&2
  exit 2
fi

COMPOSE_FILE="${ATZ_VNSTOCKS_COMPOSE:-$ROOT/docker-compose.yml}"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "missing compose: $COMPOSE_FILE" >&2
  exit 1
fi
COMPOSE=(docker compose -f "$COMPOSE_FILE")

echo "==> preflight: nginx live không được trỏ vnstocks:8501"
if docker ps --format '{{.Names}}' | grep -qx nginx-reverse-proxy; then
  if docker exec nginx-reverse-proxy sh -c \
    'grep -nE "vnstocks:8501|127.0.0.1:8501" /etc/nginx/conf.d/atz.vn.conf 2>/dev/null' \
    | grep -v '\.bak'; then
    echo "ABORT: atz.vn.conf vẫn proxy tới Streamlit :8501 — rollback nginx trước." >&2
    exit 1
  fi
  echo "    ok — atz.vn.conf không còn upstream Streamlit :8501"
else
  echo "    skip — nginx-reverse-proxy không thấy (chạy local?)"
fi

echo "==> preflight: Desk prod/dev phải healthy (nếu có)"
for url in http://127.0.0.1:8001/healthz http://127.0.0.1:8000/healthz; do
  if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
    echo "    ok $url"
  else
    echo "    warn — $url không reach (tiếp tục vì P4 chỉ tắt UI legacy)"
  fi
done

echo "==> stop + rm service UI vnstocks (giữ bot/redis)"
"${COMPOSE[@]}" stop vnstocks || true
"${COMPOSE[@]}" rm -f vnstocks || true

# Idempotent nếu container orphan ngoài compose
if docker ps -a --format '{{.Names}}' | grep -qx vnstocks; then
  docker stop vnstocks || true
  docker rm -f vnstocks || true
fi

if docker ps --format '{{.Names}}' | grep -qx vnstocks; then
  echo "FAIL: container vnstocks vẫn running" >&2
  exit 1
fi

echo "==> verify cổng :8501 không còn listen (bind host)"
if ss -lnt 2>/dev/null | grep -q ':8501'; then
  echo "warn — vẫn có process listen :8501 (không phải bắt buộc fail)" >&2
else
  echo "    ok — không thấy listen :8501"
fi

echo "==> không đụng Authentik / nginx / desk"
docker ps --format 'table {{.Names}}\t{{.Status}}' \
  | grep -E 'nginx-reverse-proxy|authentik|atz-desk|atz-redis|atz-ingestion|atz-filter|atz-alert|atz-position|atz-index|atz-ssi' \
  || true

echo
echo "DONE P4 UI: container vnstocks đã tắt/xóa."
echo "Compose: service vnstocks nên có profiles: [legacy-ui] để không tự up lại."
echo "Rollback UI (khẩn): cd $(dirname "$COMPOSE_FILE") && docker compose --profile legacy-ui up -d vnstocks"
