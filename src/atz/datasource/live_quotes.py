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


def _mget_quote_raws(
    symbols: list[str],
    *,
    client=None,
    quote_key: str = "quote:{symbol}",
    redis_url: str | None = None,
) -> tuple[list[str], list]:
    """Trả (syms, raws). raws rỗng-list nếu không kết nối."""
    syms = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not syms:
        return [], []
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
        return syms, []
    return syms, list(raws or [])


def _parse_price_k(data: dict) -> float | None:
    try:
        return _price_to_thousands(float(data["price"]))
    except (ValueError, TypeError, KeyError):
        return None


def _parse_change_pct(data: dict, price: float | None = None) -> float | None:
    raw_pct = data.get("change_pct")
    if raw_pct is not None:
        try:
            return float(raw_pct)
        except (TypeError, ValueError):
            pass
    ref = data.get("ref_price")
    try:
        ref_f = float(ref) if ref is not None else 0.0
    except (TypeError, ValueError):
        ref_f = 0.0
    if not ref_f:
        return None
    try:
        px = float(data["price"]) if price is None else float(price)
    except (TypeError, ValueError, KeyError):
        return None
    return round((px - ref_f) / ref_f * 100, 2)


def load_live_prices_thousands(
    symbols: list[str],
    *,
    client=None,
    quote_key: str = "quote:{symbol}",
    redis_url: str | None = None,
) -> dict[str, float]:
    """MGET quote → {SYMBOL: giá nghìn đồng}. Rỗng nếu không kết nối / không có key."""
    syms, raws = _mget_quote_raws(
        symbols, client=client, quote_key=quote_key, redis_url=redis_url
    )
    out: dict[str, float] = {}
    for sym, raw in zip(syms, raws):
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        price_k = _parse_price_k(data)
        if price_k is None:
            continue
        out[sym] = price_k
    return out


def load_live_session_quotes(
    symbols: list[str],
    *,
    client=None,
    quote_key: str = "quote:{symbol}",
    redis_url: str | None = None,
) -> dict[str, dict[str, float]]:
    """MGET quote → {SYMBOL: {price_k, change_pct}} cho overlay Overview Top KL.

    Cần đủ giá + % (từ ``change_pct`` hoặc ``ref_price``). Thiếu % → bỏ mã (caller giữ OHLCV).
    """
    syms, raws = _mget_quote_raws(
        symbols, client=client, quote_key=quote_key, redis_url=redis_url
    )
    out: dict[str, dict[str, float]] = {}
    for sym, raw in zip(syms, raws):
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        price_k = _parse_price_k(data)
        if price_k is None:
            continue
        change_pct = _parse_change_pct(data)
        if change_pct is None:
            continue
        out[sym] = {"price_k": float(price_k), "change_pct": float(change_pct)}
    return out
