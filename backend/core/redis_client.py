"""Read-only quote access from priceboard Redis hash."""

from __future__ import annotations

import os
from typing import Any

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")
DEFAULT_HASH = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
DEFAULT_FIELD = "last"


def get_last_price(
    symbol: str,
    *,
    redis_url: str | None = None,
    hash_key: str | None = None,
    field: str | None = None,
) -> float | None:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    url = redis_url or REDIS_URL
    hkey = hash_key or DEFAULT_HASH
    fld = field or DEFAULT_FIELD
    try:
        client = redis.from_url(url, decode_responses=True)
        try:
            raw = client.hget(hkey, sym)
            if raw is None:
                return None
            if isinstance(raw, str) and raw.startswith("{"):
                import json

                data = json.loads(raw)
                val = data.get(fld) or data.get("last") or data.get("match")
            else:
                val = raw
            if val is None or val == "":
                return None
            return float(val)
        finally:
            client.close()
    except Exception:
        return None


def batch_last_prices(
    symbols: list[str],
    **kwargs: Any,
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for sym in symbols:
        out[sym.upper()] = get_last_price(sym, **kwargs)
    return out
