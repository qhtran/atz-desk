"""Equity intraday 1m for symbol-detail chart (1d), same session rules as index spark."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from backend.board_universe import INDEX_SYMBOL_SET
from backend.index_spark import (
    INDEX_SPARK_TTL_SEC,
    MAX_SERIES_POINTS,
    is_frozen,
    minute_bucket_ts,
    should_record,
    trading_date_for,
)
from backend.market_db import (
    init_market_db,
    load_equity_minute_ohlc,
    load_equity_minute_series,
    upsert_equity_minute_bar,
)

EQUITY_SPARK_PREFIX = os.getenv("PRICEBOARD_EQUITY_SPARK_PREFIX", "priceboard:equity_spark")


def _redis_key(trading_date: str, symbol: str) -> str:
    return f"{EQUITY_SPARK_PREFIX}:{trading_date}:{symbol.upper()}"


def _parse_last(tick: dict[str, Any]) -> float | None:
    raw = tick.get("last")
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    return val


def is_equity_spark_symbol(tick: dict[str, Any]) -> bool:
    sym = str(tick.get("symbol") or "").strip().upper()
    if not sym or sym in INDEX_SYMBOL_SET:
        return False
    kind = str(tick.get("kind") or "").lower()
    if kind == "index":
        return False
    return True


def record_equity_spark_tick(tick: dict[str, Any], clock: datetime | None = None) -> bool:
    if not is_equity_spark_symbol(tick):
        return False
    if not should_record(clock):
        return False
    last = _parse_last(tick)
    if last is None:
        return False
    sym = str(tick["symbol"]).strip().upper()
    td = trading_date_for(clock)
    bucket = minute_bucket_ts(clock)
    init_market_db()
    upsert_equity_minute_bar(sym, td, bucket, last)
    return True


async def record_equity_spark(redis: Any, tick: dict[str, Any], clock: datetime | None = None) -> None:
    if not record_equity_spark_tick(tick, clock=clock):
        return
    td = trading_date_for(clock)
    sym = str(tick["symbol"]).strip().upper()
    init_market_db()
    points = load_equity_minute_series(sym, td)
    trimmed = points[-MAX_SERIES_POINTS:] if len(points) > MAX_SERIES_POINTS else points
    body = json.dumps([[ts, val] for ts, val in trimmed], separators=(",", ":"))
    await redis.set(_redis_key(td, sym), body, ex=INDEX_SPARK_TTL_SEC)


async def load_equity_intraday(
    redis: Any,
    symbol: str,
    trading_date: str | None = None,
) -> dict[str, Any]:
    sym = str(symbol or "").strip().upper()
    td = trading_date or trading_date_for()
    init_market_db()
    key = _redis_key(td, sym)
    series: list[list[float | int]] = []
    cached = await redis.get(key)
    if cached:
        try:
            series = json.loads(cached)
        except (TypeError, json.JSONDecodeError):
            series = []
    if not series:
        pts = load_equity_minute_series(sym, td)
        series = [[ts, val] for ts, val in pts]
        if series:
            await redis.set(
                key,
                json.dumps(series[-MAX_SERIES_POINTS:], separators=(",", ":")),
                ex=INDEX_SPARK_TTL_SEC,
            )
    bars_1m = load_equity_minute_ohlc(sym, td)
    return {
        "ok": True,
        "symbol": sym,
        "trading_date": td,
        "frozen": is_frozen(),
        "series": series,
        "bars_1m": bars_1m,
    }
