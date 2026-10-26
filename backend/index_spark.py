"""Index-bar intraday spark: VN session timeline, SQLite 1m + Redis cache."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from backend.board_universe import INDEX_BOARD_SYMBOLS, INDEX_SYMBOL_SET
from backend.market_db import (
    init_market_db,
    load_index_series_map,
    upsert_index_minute_bar,
)
from backend.ssi_rest_bootstrap import TZ_VN, last_trading_date_vn

INDEX_SPARK_PREFIX = os.getenv("PRICEBOARD_INDEX_SPARK_PREFIX", "priceboard:index_spark")
INDEX_SPARK_TTL_SEC = int(os.getenv("PRICEBOARD_INDEX_SPARK_TTL", str(72 * 3600)))
MAX_SERIES_POINTS = int(os.getenv("PRICEBOARD_INDEX_SPARK_MAX_POINTS", "500"))

MORNING_START = 9 * 60
MORNING_END = 11 * 60 + 30
AFTERNOON_START = 13 * 60
AFTERNOON_END = 15 * 60
SESSION_TRADING_MINUTES = (MORNING_END - MORNING_START) + (AFTERNOON_END - AFTERNOON_START)


def _vn_now(clock: datetime | None = None) -> datetime:
    if clock is None:
        return datetime.now(TZ_VN)
    if clock.tzinfo is None:
        return clock.replace(tzinfo=TZ_VN)
    return clock.astimezone(TZ_VN)


def trading_date_for(clock: datetime | None = None) -> str:
    return last_trading_date_vn(_vn_now(clock))


def _minutes_of_day(clock: datetime) -> int:
    dt = _vn_now(clock)
    return dt.hour * 60 + dt.minute


def in_trading_session(clock: datetime | None = None) -> bool:
    dt = _vn_now(clock)
    if dt.weekday() >= 5:
        return False
    mins = _minutes_of_day(dt)
    if MORNING_START <= mins <= MORNING_END:
        return True
    if AFTERNOON_START <= mins <= AFTERNOON_END:
        return True
    return False


def should_record(clock: datetime | None = None) -> bool:
    return in_trading_session(clock)


def is_frozen(clock: datetime | None = None) -> bool:
    return not in_trading_session(clock)


def trading_session_x(clock: datetime | None = None) -> float:
    """Map VN clock into [0, 1] over 270 session minutes (morning + afternoon)."""
    dt = _vn_now(clock)
    mins = _minutes_of_day(dt)
    if mins < MORNING_START:
        return 0.0
    if mins <= MORNING_END:
        return (mins - MORNING_START) / SESSION_TRADING_MINUTES
    if mins < AFTERNOON_START:
        return (MORNING_END - MORNING_START) / SESSION_TRADING_MINUTES
    if mins <= AFTERNOON_END:
        elapsed = (MORNING_END - MORNING_START) + (mins - AFTERNOON_START)
        return elapsed / SESSION_TRADING_MINUTES
    return 1.0


def minute_bucket_ts(clock: datetime | None = None) -> int:
    dt = _vn_now(clock)
    floored = dt.replace(second=0, microsecond=0)
    return int(floored.timestamp())


def _redis_key(trading_date: str, symbol: str) -> str:
    return f"{INDEX_SPARK_PREFIX}:{trading_date}:{symbol.upper()}"


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


def is_index_spark_symbol(tick: dict[str, Any]) -> bool:
    sym = str(tick.get("symbol") or "").strip().upper()
    if sym not in INDEX_SYMBOL_SET:
        return False
    kind = str(tick.get("kind") or "").lower()
    return kind == "index"


def record_index_spark_tick(tick: dict[str, Any], clock: datetime | None = None) -> bool:
    """Persist one index tick into 1m SQLite bar when inside session."""
    if not is_index_spark_symbol(tick):
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
    upsert_index_minute_bar(sym, td, bucket, last)
    return True


async def refresh_index_spark_redis(redis: Any, trading_date: str | None = None) -> None:
    """Sync Redis cache from SQLite for all index-board symbols."""
    td = trading_date or trading_date_for()
    init_market_db()
    series = load_index_series_map(list(INDEX_BOARD_SYMBOLS), td)
    for sym, points in series.items():
        trimmed = points[-MAX_SERIES_POINTS:] if len(points) > MAX_SERIES_POINTS else points
        body = json.dumps(trimmed, separators=(",", ":"))
        key = _redis_key(td, sym)
        await redis.set(key, body, ex=INDEX_SPARK_TTL_SEC)


async def record_index_spark(redis: Any, tick: dict[str, Any], clock: datetime | None = None) -> None:
    if not record_index_spark_tick(tick, clock=clock):
        return
    td = trading_date_for(clock)
    sym = str(tick["symbol"]).strip().upper()
    init_market_db()
    points = load_index_series_map([sym], td).get(sym, [])
    trimmed = points[-MAX_SERIES_POINTS:] if len(points) > MAX_SERIES_POINTS else points
    await redis.set(
        _redis_key(td, sym),
        json.dumps(trimmed, separators=(",", ":")),
        ex=INDEX_SPARK_TTL_SEC,
    )


async def load_index_spark(
    redis: Any,
    symbols: list[str] | None = None,
    trading_date: str | None = None,
) -> dict[str, Any]:
    syms = [s.strip().upper() for s in (symbols or list(INDEX_BOARD_SYMBOLS)) if s]
    td = trading_date or trading_date_for()
    init_market_db()
    out: dict[str, list[list[float | int]]] = {}
    for sym in syms:
        if sym not in INDEX_SYMBOL_SET:
            continue
        key = _redis_key(td, sym)
        cached = await redis.get(key)
        if cached:
            try:
                out[sym] = json.loads(cached)
                continue
            except (TypeError, json.JSONDecodeError):
                pass
        pts = load_index_series_map([sym], td).get(sym, [])
        out[sym] = pts
        if pts:
            await redis.set(
                key,
                json.dumps(pts[-MAX_SERIES_POINTS:], separators=(",", ":")),
                ex=INDEX_SPARK_TTL_SEC,
            )
    return {
        "ok": True,
        "trading_date": td,
        "frozen": is_frozen(),
        "series": out,
    }
