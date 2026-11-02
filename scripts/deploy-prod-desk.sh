#!/usr/bin/env bash
# Start ATZ Desk prod-desk stack on :8001 (ADR 0009 prep).
# Does NOT apply nginx atz.vn. Does NOT touch desk-dev :8000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE=(docker compose -f docker-compose.prod-desk.yml)

if [[ ! -f .env.prod-desk ]]; then
  if [[ -f .env.prod-desk.example ]]; then
    cp .env.prod-desk.example .env.prod-desk
    echo "created .env.prod-desk from example — điền SSI secret trước khi --profile live"
  else
    echo "missing .env.prod-desk.example" >&2
    exit 1
  fi
fi

echo "==> build/up prod-desk (api+redis; ssi-worker cần --profile live)"
"${COMPOSE[@]}" up -d --build

echo "==> wait healthz http://127.0.0.1:8001/healthz"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8001/healthz >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" -ne 1 ]]; then
  echo "healthz FAIL — logs:" >&2
  "${COMPOSE[@]}" logs api --tail 40 >&2 || true
  exit 1
fi
curl -fsS http://127.0.0.1:8001/healthz
echo
echo "Prod Desk API healthy on :8001"
echo "NOTE: deploy/nginx_prod_atz.conf is DRAFT only — not applied (use apply-prod-atz-nginx.sh + ATZ_APPLY_PROD_NGINX=1 after gate)."
