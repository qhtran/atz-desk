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
    load_equity_series_map,
    upsert_equity_minute_bar,
)

EQUITY_SPARK_PREFIX = os.getenv("PRICEBOARD_EQUITY_SPARK_PREFIX", "priceboard:equity_spark")
EQUITY_SPARK_MAX_SYMBOLS = int(os.getenv("PRICEBOARD_EQUITY_SPARK_MAX_SYMBOLS", "400"))


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


def _normalize_equity_symbols(symbols: list[str] | None) -> list[str]:
    """Dedupe, drop index-bar symbols, cap list size for board hydrate."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in symbols or []:
        sym = str(raw or "").strip().upper()
        if not sym or sym in INDEX_SYMBOL_SET or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
        if len(out) >= EQUITY_SPARK_MAX_SYMBOLS:
            break
    return out


async def load_equity_spark(
    redis: Any,
    symbols: list[str] | None = None,
    trading_date: str | None = None,
) -> dict[str, Any]:
    """Bulk 1m close series for iBoard XHT column (same cache shape as index-spark)."""
    syms = _normalize_equity_symbols(symbols)
    td = trading_date or trading_date_for()
    init_market_db()
    out: dict[str, list[list[float | int]]] = {}
    missing: list[str] = []
    for sym in syms:
        key = _redis_key(td, sym)
        cached = await redis.get(key)
        if cached:
            try:
                out[sym] = json.loads(cached)
                continue
            except (TypeError, json.JSONDecodeError):
                pass
        missing.append(sym)
    if missing:
        from_db = load_equity_series_map(missing, td)
        for sym in missing:
            pts = from_db.get(sym, [])
            out[sym] = pts
            if pts:
                trimmed = pts[-MAX_SERIES_POINTS:] if len(pts) > MAX_SERIES_POINTS else pts
                await redis.set(
                    _redis_key(td, sym),
                    json.dumps(trimmed, separators=(",", ":")),
                    ex=INDEX_SPARK_TTL_SEC,
                )
    return {
        "ok": True,
        "trading_date": td,
        "frozen": is_frozen(),
        "series": out,
    }
