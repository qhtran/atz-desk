#!/usr/bin/env bash
# Smoke check dev.atz.vn stack trước merge/push/deploy (local).
#
#   ./scripts/check-dev.sh              # pytest + docker healthz + API smoke
#   ./scripts/check-dev.sh --pytest-only  # chỉ pytest (nhanh)
#   ./scripts/check-dev.sh --no-build     # docker up không rebuild image
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose.dev.yml"
PYTEST_ONLY=0
DOCKER_BUILD=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pytest-only) PYTEST_ONLY=1 ;;
    --no-build) DOCKER_BUILD=0 ;;
    -h | --help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

# Tập pytest gần priceboard dev (backend + advisor; không cần Redis prod).
SMOKE_TESTS=(
  tests/test_daily_signals.py
  tests/test_board_universe.py
  tests/test_advisor_score.py
  tests/test_advisor_filter.py
  tests/test_filter_runner_advisor.py
  tests/test_screener.py
  tests/test_volume_filter.py
  tests/test_tick_contract.py
  tests/test_priceboard_observability.py
  tests/test_debug_ui.py
  tests/test_portfolio_store.py
  tests/test_portfolio_quotes.py
  tests/test_ohlcv_seed.py
)

run_pytest() {
  echo "==> pytest smoke (${#SMOKE_TESTS[@]} files)"
  if ! command -v pytest >/dev/null 2>&1; then
    echo "pytest không có trong PATH — thử: pip install -r backend/requirements.txt" >&2
    exit 1
  fi
  (
    cd "$ROOT"
    export PYTHONPATH="${ROOT}/src/atz:${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
    pytest -q "${SMOKE_TESTS[@]}"
  )
  echo "pytest: OK"
}

run_docker_smoke() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker không có — bỏ qua docker smoke (dùng --pytest-only để chủ đích)" >&2
    exit 1
  fi
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Thiếu $COMPOSE_FILE" >&2
    exit 1
  fi

  echo "==> docker compose (redis + api)"
  local -a build_args=()
  if [[ "$DOCKER_BUILD" -eq 1 ]]; then
    build_args=(--build)
  fi
  docker compose -f "$COMPOSE_FILE" up -d "${build_args[@]}" redis api

  echo "==> waiting for http://127.0.0.1:8000/healthz"
  local ok=0
  for _ in $(seq 1 45); do
    if curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 2
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "healthz: FAIL — logs: docker compose -f $COMPOSE_FILE logs api --tail 50" >&2
    exit 1
  fi
  curl -fsS http://127.0.0.1:8000/healthz && echo ""

  echo "==> GET /api/iboard/daily-signals/filters"
  local filters
  filters="$(curl -fsS http://127.0.0.1:8000/api/iboard/daily-signals/filters)"
  echo "$filters"
  if ! grep -q '"advisor"' <<<"$filters"; then
    echo "filters thiếu advisor — rebuild api: docker compose -f $COMPOSE_FILE build api" >&2
    exit 1
  fi
  echo "==> GET /api/iboard/symbol-bars?symbol=VIC&range=1y"
  local bars_json
  bars_json="$(curl -fsS "http://127.0.0.1:8000/api/iboard/symbol-bars?symbol=VIC&range=1y")"
  if ! grep -q '"close"' <<<"$bars_json"; then
    echo "symbol-bars trống — seed OHLCV: ./scripts/seed-iboard-ohlcv.sh" >&2
    exit 1
  fi
  echo "docker smoke: OK"
}

echo "==> check-dev (root=$ROOT)"
run_pytest
if [[ "$PYTEST_ONLY" -eq 0 ]]; then
  run_docker_smoke
else
  echo "==> skip docker (--pytest-only)"
fi
echo "==> PASS — OK merge/push/deploy dev"
