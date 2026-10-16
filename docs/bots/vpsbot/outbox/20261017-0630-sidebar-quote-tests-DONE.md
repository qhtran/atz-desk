# Outbox VPSbot — sidebar quote tests

- **Status:** DONE
- **Brief:** `docs/bots/vpsbot/inbox/20261017-0630-sidebar-quote-tests.md`
- **HEAD (code):** `f674881`
- **Deploy:** no (brief `deploy: no`) — test-only change, no service restarted
- **Merge main:** yes — committed and pushed directly to `main` (fast-forward, no force)

## Summary

Added `tests/test_sidebar_portfolio.py` covering the sidebar quote path with a
mocked Redis (no live Redis needed): Redis hit, Redis miss → per-symbol OHLCV
fallback, Redis outage (ConnectionError / TimeoutError / OSError) → `{}` → OHLCV,
unknown symbol with no price at all, malformed quote payloads, blank/NaN desk
symbols, P&L from live price, and `position_alert` bands/zones.
No production code changed.

## Files

- `tests/test_sidebar_portfolio.py` (new, 15 tests)
- This outbox file

## Tests

- `pytest tests/test_sidebar_portfolio.py tests/test_live_quotes.py` → **Pass** (19 passed in 1.39s)

## Coverage map (brief → test)

| Brief case | Tests |
|------------|-------|
| Redis hit | `test_redis_hit_normalises_symbols_and_converts_units`, `test_redis_custom_quote_key`, `test_rows_redis_hit_beats_ohlcv` |
| Redis miss → OHLCV fallback | `test_rows_redis_miss_falls_back_to_ohlcv_per_symbol`, `test_rows_redis_down_uses_ohlcv`, `test_redis_error_returns_empty` |
| Symbol không có | `test_unknown_symbol_is_dropped`, `test_rows_unknown_symbol_without_any_price` |
| Quote stale | **Skipped** — `datasource/live_quotes.py` has no staleness flag/timestamp check yet |
| Extra | malformed payloads, empty symbol list skips Redis, blank/NaN rows, P&L, `position_alert` |

## Commands run (VPS `/opt/vnstocks`, SSH:443)

```
git pull --ff-only origin main
docker run --rm --network vnstocks_realtime -v /opt/vnstocks:/src:ro --tmpfs /src/data \
  -w /src -e PYTHONPATH=/src/src vnstocks-vnstocks \
  python -m pytest -q -p no:cacheprovider tests/test_sidebar_portfolio.py tests/test_live_quotes.py
git commit -m "test(sidebar): cover Redis hit, miss/outage fallback and unknown symbols"
git push origin main
```

## Services

- None restarted (deploy: no).

## Notes / remaining risk

- Stale quotes are still shown as live: if a `quote:{symbol}` key outlives the
  session, the sidebar labels it `redis`. Adding a timestamp/TTL check would be a
  separate brief (needs the ingestion payload's time field).
- Untouched: nginx / SSH / firewall / Authentik / `.env`, Filter F1 (brief `0700`, next poll).
