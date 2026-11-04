"""On-demand SSI watchlist (P1) — Redis touch + idle expiry.

Redis hash ``priceboard:ondemand``: field=SYMBOL, value=unix_ts (last touch).
API/FE touches symbols outside Core; ``ssi_live`` polls and SUBSCRIBE/UNSUBSCRIBE.
"""

from __future__ import annotations

import os
import time
from typing import Any

import redis

from backend.market_catalog import load_core_symbol_set
from backend.portfolio_quotes import normalize_symbols
from backend.redis_listener import REDIS_URL

ONDEMAND_HASH = os.getenv("PRICEBOARD_ONDEMAND_HASH", "priceboard:ondemand")
ONDEMAND_IDLE_SEC = float(os.getenv("PRICEBOARD_ONDEMAND_IDLE_SEC", str(30 * 60)))
ONDEMAND_MAX = int(os.getenv("PRICEBOARD_ONDEMAND_MAX", "40"))


def touch_ondemand_symbols(
    symbols: str | list[str],
    *,
    redis_url: str = REDIS_URL,
    hash_key: str = ONDEMAND_HASH,
    idle_sec: float = ONDEMAND_IDLE_SEC,
    max_symbols: int = ONDEMAND_MAX,
    now: float | None = None,
    skip_core: bool = True,
    client: redis.Redis | None = None,
) -> dict[str, Any]:
    """Touch off-core symbols in Redis. Returns summary for API."""
    syms = normalize_symbols(symbols)
    core = load_core_symbol_set() if skip_core else frozenset()
    wanted = [s for s in syms if s not in core]
    skipped_core = [s for s in syms if s in core]
    ts = float(now if now is not None else time.time())
    if not wanted:
        return {
            "ok": True,
            "touched": [],
            "skipped_core": skipped_core,
            "rejected": [],
            "active": 0,
            "idle_sec": idle_sec,
            "max": max_symbols,
        }

    owned = client is None
    rejected: list[str] = []
    touched: list[str] = []
    try:
        if client is None:
            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        raw = client.hgetall(hash_key) or {}
        # drop expired
        for sym, val in list(raw.items()):
            try:
                last = float(val)
            except (TypeError, ValueError):
                client.hdel(hash_key, sym)
                continue
            if ts - last > idle_sec:
                client.hdel(hash_key, sym)
                raw.pop(sym, None)

        active = set(raw.keys())
        for sym in wanted:
            if sym in active:
                client.hset(hash_key, sym, str(ts))
                touched.append(sym)
                continue
            if len(active) >= max_symbols:
                rejected.append(sym)
                continue
            client.hset(hash_key, sym, str(ts))
            active.add(sym)
            touched.append(sym)

        active_n = client.hlen(hash_key)
    except (redis.exceptions.RedisError, OSError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "touched": [],
            "skipped_core": skipped_core,
            "rejected": wanted,
            "active": 0,
            "idle_sec": idle_sec,
            "max": max_symbols,
        }
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:
                pass

    return {
        "ok": True,
        "touched": touched,
        "skipped_core": skipped_core,
        "rejected": rejected,
        "active": int(active_n or 0),
        "idle_sec": idle_sec,
        "max": max_symbols,
    }


def list_active_ondemand(
    *,
    redis_url: str = REDIS_URL,
    hash_key: str = ONDEMAND_HASH,
    idle_sec: float = ONDEMAND_IDLE_SEC,
    now: float | None = None,
    client: redis.Redis | None = None,
) -> list[str]:
    """Return non-expired on-demand symbols (and prune expired)."""
    ts = float(now if now is not None else time.time())
    owned = client is None
    try:
        if client is None:
            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        raw = client.hgetall(hash_key) or {}
        active: list[str] = []
        for sym, val in raw.items():
            try:
                last = float(val)
            except (TypeError, ValueError):
                client.hdel(hash_key, sym)
                continue
            if ts - last > idle_sec:
                client.hdel(hash_key, sym)
                continue
            active.append(str(sym).upper())
        active.sort()
        return active
    except (redis.exceptions.RedisError, OSError):
        return []
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:
                pass
