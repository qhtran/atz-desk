"""Giá nóng từ Redis quote:{symbol} → nghìn đồng (cùng đơn vị desk/OHLCV).

Redis miss / lỗi → caller fallback OHLCV. Không commit secret; URL từ config YAML.
"""

from __future__ import annotations

import json
import logging

import redis

log = logging.getLogger(__name__)


def _price_to_thousands(price: float) -> float:
    """Quote Redis thường VND đầy đủ; desk dùng nghìn đồng."""
    if price >= 1000:
        return round(price / 1000.0, 2)
    return float(price)


def load_live_prices_thousands(
    symbols: list[str],
    *,
    client=None,
    quote_key: str = "quote:{symbol}",
    redis_url: str | None = None,
) -> dict[str, float]:
    """MGET quote → {SYMBOL: giá nghìn đồng}. Rỗng nếu không kết nối / không có key."""
    syms = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not syms:
        return {}
    try:
        if client is None:
            if not redis_url:
                from ui_realtime import config as ui_config

                cfg = ui_config.load()
                redis_url = cfg["redis"]["url"]
                quote_key = cfg["ui_realtime"].get("quote_key", quote_key)
            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        keys = [quote_key.format(symbol=s) for s in syms]
        raws = client.mget(keys)
    except (redis.exceptions.RedisError, OSError, KeyError, TypeError) as exc:
        log.debug("live_quotes miss: %s", exc)
        return {}

    out: dict[str, float] = {}
    for sym, raw in zip(syms, raws or []):
        if not raw:
            continue
        try:
            data = json.loads(raw)
            price = float(data["price"])
        except (ValueError, TypeError, KeyError):
            continue
        out[sym] = _price_to_thousands(price)
    return out
