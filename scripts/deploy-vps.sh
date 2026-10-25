#!/usr/bin/env bash
# Deploy vnstocks lên VPS qua SSH (git pull + docker compose).
#
# Cấu hình: copy scripts/deploy-vps.env.example → scripts/deploy-vps.env (không commit).
#
# Ví dụ:
#   ./scripts/deploy-vps.sh dev
#   ./scripts/deploy-vps.sh dev --push
#   ./scripts/deploy-vps.sh prod
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/scripts/deploy-vps.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$ENV_FILE"
fi

: "${ATZ_VPS_SSH:?Set ATZ_VPS_SSH in scripts/deploy-vps.env (vd. vps hoặc user@host)}"
: "${ATZ_VPS_DIR:=/opt/vnstocks}"

TARGET="${1:-dev}"
shift || true

DO_PUSH=0
DRY_RUN=0
PROD_NO_DEPS=1
EXTRA_SERVICES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push) DO_PUSH=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --no-deps) PROD_NO_DEPS=1 ;;
    --with-deps) PROD_NO_DEPS=0 ;;
    --services)
      shift
      EXTRA_SERVICES="${1:?--services requires value}"
      ;;
    -h | --help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

BRANCH="${ATZ_VPS_BRANCH:-$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)}"

if [[ "$DO_PUSH" -eq 1 ]]; then
  echo "==> git push origin ${BRANCH}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "(dry-run) git -C $ROOT push -u origin HEAD"
  else
    git -C "$ROOT" push -u origin HEAD
  fi
fi

run_remote() {
  local compose_file="$1"
  local build_services="$2"
  local up_services="$3"
  local up_flags="$4"

  local remote_script
  remote_script="$(cat <<'EOF'
set -euo pipefail
ATZ_VPS_DIR=$1
ATZ_VPS_BRANCH=$2
ATZ_COMPOSE_FILE=$3
ATZ_BUILD_SERVICES=$4
ATZ_UP_SERVICES=$5
ATZ_UP_FLAGS=$6
shift 6 || true
cd "${ATZ_VPS_DIR:?}"
echo "==> VPS: $(hostname) · $(pwd)"
echo "==> branch ${ATZ_VPS_BRANCH:?}"
git fetch origin
git checkout "${ATZ_VPS_BRANCH}"
git pull --ff-only origin "${ATZ_VPS_BRANCH}"
read -r -a _build <<< "${ATZ_BUILD_SERVICES}"
read -r -a _up <<< "${ATZ_UP_SERVICES}"
echo "==> docker compose -f ${ATZ_COMPOSE_FILE} build ${_build[*]}"
docker compose -f "${ATZ_COMPOSE_FILE}" build "${_build[@]}"
_up_cmd=(docker compose -f "${ATZ_COMPOSE_FILE}" up -d)
if [[ -n "${ATZ_UP_FLAGS:-}" ]]; then _up_cmd+=("${ATZ_UP_FLAGS}"); fi
_up_cmd+=("${_up[@]}")
echo "==> ${_up_cmd[*]}"
"${_up_cmd[@]}"
docker compose -f "${ATZ_COMPOSE_FILE}" ps
if [[ "${ATZ_COMPOSE_FILE}" == "docker-compose.dev.yml" ]]; then
  echo "==> waiting for healthz (api start_period ~20s)..."
  _hz_ok=0
  for _i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
      _hz_ok=1
      break
    fi
    sleep 2
  done
  if [[ "$_hz_ok" -eq 1 ]]; then
    curl -fsS http://127.0.0.1:8000/healthz && echo ""
    echo "healthz: OK"
  else
    echo "healthz: FAIL sau 60s — xem: docker compose -f ${ATZ_COMPOSE_FILE} logs api --tail 40" >&2
    exit 1
  fi
fi
EOF
)"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "==> dry-run SSH ${ATZ_VPS_SSH}"
    echo "    ATZ_VPS_DIR=$ATZ_VPS_DIR ATZ_VPS_BRANCH=$BRANCH"
    echo "    compose=$compose_file build=[$build_services] up=[$up_flags $up_services]"
    return 0
  fi

  ssh "$ATZ_VPS_SSH" bash -s -- \
    "$ATZ_VPS_DIR" \
    "$BRANCH" \
    "$compose_file" \
    "$build_services" \
    "$up_services" \
    "$up_flags" <<<"$remote_script"
}

case "$TARGET" in
  dev)
    services="${EXTRA_SERVICES:-api ssi-worker}"
    run_remote "docker-compose.dev.yml" "$services" "$services" ""
    ;;
  prod)
    services="${EXTRA_SERVICES:-vnstocks}"
    up_flags=""
    if [[ "$PROD_NO_DEPS" -eq 1 ]]; then
      up_flags="--no-deps"
    fi
    run_remote "docker-compose.yml" "$services" "$services" "$up_flags"
    ;;
  *)
    echo "Usage: $0 {dev|prod} [--push] [--dry-run] [--services \"a b\"]" >&2
    echo "  dev  — dev.atz.vn (docker-compose.dev.yml, mặc định api ssi-worker)" >&2
    echo "  prod — atz.vn (docker-compose.yml, mặc định vnstocks --no-deps)" >&2
    exit 2
    ;;
esac

echo "==> Done ($TARGET · branch $BRANCH)"
