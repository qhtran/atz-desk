# Outbox VPSbot — sidebar live quote

- **Status:** DONE
- **Brief:** `docs/bots/vpsbot/inbox/20261017-0622-sidebar-live-quote.md`
- **HEAD (code deployed):** `0816526`
- **Deploy:** yes — service `vnstocks` rebuilt + recreated (2026-10-16T23:35Z UTC)
- **Merge main:** not needed — architect code was already on `main`

## Summary

Verified the architect's sidebar live-quote code already on `main`
(`datasource/live_quotes.py`, Redis `quote:{symbol}` → nghìn đồng with OHLCV
fallback in `ui/sidebar_portfolio.py`). Tests pass, no code changes needed.
Unit check: Redis quotes are full VND (e.g. `quote:LPB` price `38000.0`),
`_price_to_thousands` converts to `38.0` → matches desk/OHLCV unit. No unit bug.
Deployed `vnstocks` only.

## Files

- No code changes.
- `docs/F1_CHECKLIST_UI.md` §2 — realtime-quote checkbox already ticked `[x]` on main (no edit).
- Added this outbox file.

## Tests

- `pytest tests/test_live_quotes.py tests/test_capital_ledger.py` → **Pass** (7 passed in 1.42s)
- Smoke inside new `vnstocks` container: `load_live_prices_thousands(["LPB","MSN","FPT","ZZZZ"])`
  → `{'LPB': 38.0, 'MSN': 71.4, 'FPT': 58.2}` (unknown symbol dropped → OHLCV fallback path)
- Streamlit health `/_stcore/health` → `ok`

## Commands run (VPS `/opt/vnstocks`, SSH:443)

```
git pull --ff-only origin main
docker run --rm --network vnstocks_realtime -v /opt/vnstocks:/src:ro --tmpfs /src/data \
  -w /src -e PYTHONPATH=/src/src vnstocks-vnstocks \
  python -m pytest -q -p no:cacheprovider tests/test_live_quotes.py tests/test_capital_ledger.py
DOCKER_BUILDKIT=1 docker compose build vnstocks      # BUILD_EXIT=0
docker compose up -d --no-deps vnstocks              # Recreated, Started
docker compose ps vnstocks                           # Up
```

## Services

- Restarted: `vnstocks` only. Other services (ingestion, filter-runner, alert-dispatcher,
  position-monitor, index-feed, redis) untouched and healthy.

## Notes / remaining risk

- `vnstocks` container has no healthcheck in compose (status shows `Up`, not `healthy`); health endpoint checked manually.
- `_price_to_thousands` uses a `>= 1000` heuristic; fine for current HOSE/HNX prices, but a quote
  already in nghìn đồng ≥ 1000 (none today) would be mis-scaled.
- Untouched: nginx / SSH / firewall / Authentik / `.env`, Filter F1 (brief `0700`).
