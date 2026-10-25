#!/usr/bin/env bash
# Refresh data/ohlcv cho iBoard «Tín hiệu ngày» (dev.atz.vn).
#
# VPS: host thường không có vnstock — script seed qua container prod `vnstocks` (rw data/ohlcv).
# Local: nếu không có container, fallback `python3 -m backend.ohlcv_seed` (venv + requirements.txt).
#
#   ./scripts/seed-iboard-ohlcv.sh
#   ./scripts/seed-iboard-ohlcv.sh --market VN30 --limit 5
#   ./scripts/seed-iboard-ohlcv.sh --no-restart-api
#   ./scripts/seed-iboard-ohlcv.sh --dry-run
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose.dev.yml"
CONTAINER="${ATZ_OHLCV_SEED_CONTAINER:-vnstocks}"
MARKET="ALL"
LIMIT=0
DRY_RUN=0
RESTART_API=1
SLEEP="0.35"

usage() {
  sed -n '2,12p' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --market) MARKET="${2:?--market requires value}"; shift ;;
    --limit) LIMIT="${2:?--limit requires value}"; shift ;;
    --sleep) SLEEP="${2:?--sleep requires value}"; shift ;;
    --container) CONTAINER="${2:?--container requires value}"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    --no-restart-api) RESTART_API=0 ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

symbol_list() {
  (
    cd "$ROOT"
    export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
    SEED_MARKET="$MARKET" python3 - <<'PY'
import os
from backend.ohlcv_seed import collect_symbols, parse_markets

market = os.environ["SEED_MARKET"]
for sym in collect_symbols(parse_markets(market)):
    print(sym)
PY
  )
}

symbols=()
while IFS= read -r line; do
  [[ -n "$line" ]] && symbols+=("$line")
done < <(symbol_list)

if [[ "$LIMIT" -gt 0 && "${#symbols[@]}" -gt "$LIMIT" ]]; then
  symbols=("${symbols[@]:0:$LIMIT}")
fi

echo "==> market=${MARKET} symbols=${#symbols[@]} dry_run=${DRY_RUN}"

if [[ "${#symbols[@]}" -eq 0 ]]; then
  echo "Không có mã để seed." >&2
  exit 1
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '%s\n' "${symbols[@]}"
  exit 0
fi

seed_via_module() {
  (
    cd "$ROOT"
    export PYTHONPATH="${ROOT}/src/atz:${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
    local -a args=(--market "$MARKET" --sleep "$SLEEP")
    [[ "$LIMIT" -gt 0 ]] && args+=(--limit "$LIMIT")
    python3 -m backend.ohlcv_seed "${args[@]}"
  )
}

seed_via_docker() {
  local list_file
  list_file="$(mktemp)"
  trap 'rm -f "$list_file"' EXIT
  printf '%s\n' "${symbols[@]}" >"$list_file"

  docker cp "$list_file" "${CONTAINER}:/tmp/iboard_seed_symbols.txt"
  docker exec -w /app/src/atz "$CONTAINER" python3 -c "
from datetime import date, timedelta
import time
from config import CHART_DAYS
from datasource.client import load_bars

syms = [l.strip() for l in open('/tmp/iboard_seed_symbols.txt') if l.strip()]
start = (date.today() - timedelta(days=int(CHART_DAYS))).isoformat()
sleep_s = float('${SLEEP}')
ok = fail = 0
for i, s in enumerate(syms):
    try:
        f = load_bars(s, start)
        if f is not None and not f.empty:
            ok += 1
        else:
            fail += 1
    except Exception:
        fail += 1
    if i + 1 < len(syms) and sleep_s > 0:
        time.sleep(sleep_s)
    if (i + 1) % 20 == 0:
        print(f'progress {i + 1}/{len(syms)} ok={ok} fail={fail}', flush=True)
print(f'DONE total={len(syms)} ok={ok} fail={fail}')
raise SystemExit(0 if fail == 0 else 1)
"
}

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "==> seed qua docker container: ${CONTAINER}"
  seed_via_docker
elif python3 -c "import vnstock" >/dev/null 2>&1; then
  echo "==> seed local (python3 -m backend.ohlcv_seed)"
  seed_via_module
else
  echo "Không có container ${CONTAINER} và không import được vnstock — cần một trong hai." >&2
  exit 1
fi

if [[ "$RESTART_API" -eq 1 && -f "$COMPOSE_FILE" ]]; then
  if docker compose -f "$COMPOSE_FILE" ps api --status running -q 2>/dev/null | grep -q .; then
    echo "==> restart dev api (xóa cache daily-signals in-memory)"
    docker compose -f "$COMPOSE_FILE" restart api
  fi
fi

echo "seed-iboard-ohlcv: OK"
