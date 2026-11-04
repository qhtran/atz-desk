"""Static/snapshot quotes for symbols outside Core WS stream (P0).

Resolution order per symbol:
  1. Redis priceboard hash (live or last WS tick)
  2. OHLCV daily CSV last close (same path as portfolio quotes)
  3. Catalog stub (known symbol, no price yet)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import redis

from backend.board_universe import exchange_for_symbol
from backend.market_catalog import get_catalog_symbol, load_core_symbol_set
from backend.portfolio_quotes import (
    DEFAULT_BARS_DIR,
    normalize_symbols,
    ohlcv_last_close_vnd,
)
from backend.redis_listener import HASH_KEY, REDIS_URL
from backend.tick_contract import build_tick, tick_kind_for_symbol


def _parse_hash_tick(payload: str | None) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        row = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(row, dict):
        return None
    sym = str(row.get("symbol") or "").strip().upper()
    if not sym:
        return None
    return row


def _load_hash_rows(
    symbols: list[str],
    *,
    redis_url: str = REDIS_URL,
    hash_key: str = HASH_KEY,
    client: redis.Redis | None = None,
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    owned = client is None
    try:
        if client is None:
            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        pipe = client.pipeline()
        for sym in symbols:
            pipe.hget(hash_key, sym)
        raw_list = pipe.execute()
    except (redis.exceptions.RedisError, OSError):
        return {}
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:
                pass
    out: dict[str, dict[str, Any]] = {}
    for sym, payload in zip(symbols, raw_list):
        tick = _parse_hash_tick(payload if isinstance(payload, str) else None)
        if tick:
            out[sym] = tick
    return out


def _ohlcv_tick(symbol: str, bars_dir: Path) -> dict[str, Any] | None:
    px = ohlcv_last_close_vnd(bars_dir, symbol)
    if px is None or px <= 0:
        return None
    return build_tick(
        symbol=symbol,
        last=px,
        ref=px,
        kind=tick_kind_for_symbol(symbol),
        exchange=exchange_for_symbol(symbol),
        volume=0,
        change=0,
        change_pct=0.0,
        source="OHLCV_SNAP",
        extra={"bootstrap": "ohlcv_snapshot"},
    )


def _catalog_stub(symbol: str) -> dict[str, Any] | None:
    meta = get_catalog_symbol(symbol)
    if not meta:
        return None
    return {
        "type": "tick",
        "symbol": symbol,
        "exchange": meta.get("exchange") or exchange_for_symbol(symbol),
        "kind": tick_kind_for_symbol(symbol),
        "last": None,
        "ref": None,
        "change": None,
        "change_pct": None,
        "volume": 0,
        "source": "CATALOG",
        "in_core": bool(meta.get("in_core")),
        "name": meta.get("name") or "",
        "priced": False,
    }


def resolve_quote_snapshots(
    symbols: str | list[str],
    *,
    bars_dir: Path | None = None,
    redis_url: str = REDIS_URL,
    hash_key: str = HASH_KEY,
    priceboard_rows: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return ``{ok, quotes, core_hits, ohlcv_hits, catalog_only, missing}``."""
    syms = normalize_symbols(symbols)
    core = load_core_symbol_set()
    bars = Path(bars_dir or os.getenv("OHLCV_BARS_DIR", DEFAULT_BARS_DIR))
    hash_rows = (
        priceboard_rows
        if priceboard_rows is not None
        else _load_hash_rows(syms, redis_url=redis_url, hash_key=hash_key)
    )

    quotes: dict[str, dict[str, Any]] = {}
    core_hits = 0
    ohlcv_hits = 0
    catalog_only = 0
    missing: list[str] = []

    for sym in syms:
        row = hash_rows.get(sym)
        if row and (row.get("last") not in (None, "", 0) or row.get("ref") not in (None, "", 0)):
            out = dict(row)
            out["symbol"] = sym
            out["in_core"] = sym in core
            out["priced"] = True
            out["snap_source"] = "priceboard"
            quotes[sym] = out
            if sym in core:
                core_hits += 1
            continue

        ohlcv = _ohlcv_tick(sym, bars)
        if ohlcv:
            ohlcv["in_core"] = sym in core
            ohlcv["priced"] = True
            ohlcv["snap_source"] = "ohlcv"
            quotes[sym] = ohlcv
            ohlcv_hits += 1
            continue

        stub = _catalog_stub(sym)
        if stub:
            stub["snap_source"] = "catalog"
            quotes[sym] = stub
            catalog_only += 1
            continue

        missing.append(sym)

    return {
        "ok": True,
        "quotes": quotes,
        "core_hits": core_hits,
        "ohlcv_hits": ohlcv_hits,
        "catalog_only": catalog_only,
        "missing": missing,
        "requested": len(syms),
    }
