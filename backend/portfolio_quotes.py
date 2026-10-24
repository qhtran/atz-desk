"""Portfolio quote batch: priceboard hash → OHLCV → legacy quote:* (wl_rows parity)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import redis

from backend.redis_listener import HASH_KEY, REDIS_URL

AVG_VOLUME_BARS = 10
DEFAULT_BARS_DIR = Path(os.getenv("OHLCV_BARS_DIR", "data/ohlcv"))
LEGACY_QUOTE_KEY = os.getenv("LEGACY_QUOTE_KEY", "quote:{symbol}")


def normalize_symbols(raw: str | list[str]) -> list[str]:
    if isinstance(raw, str):
        parts = raw.split(",")
    else:
        parts = list(raw)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        sym = str(p).strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def _desk_to_vnd(value: float) -> float:
    """Nghìn đồng (OHLCV / legacy desk) → VND cho SPA fmtPrice."""
    if value >= 1000:
        return round(value)
    return round(value * 1000)


def _parse_priceboard_last(payload: str) -> float | None:
    try:
        row = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    last = row.get("last")
    if last is None:
        return None
    try:
        px = float(last)
    except (TypeError, ValueError):
        return None
    return px if px > 0 else None


def load_priceboard_prices(
    symbols: list[str],
    *,
    redis_url: str = REDIS_URL,
    hash_key: str = HASH_KEY,
    client: redis.Redis | None = None,
) -> dict[str, float]:
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
        raw = client.hgetall(hash_key)
    except (redis.exceptions.RedisError, OSError):
        return {}
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:
                pass
    out: dict[str, float] = {}
    for sym in symbols:
        payload = raw.get(sym)
        if not payload:
            continue
        px = _parse_priceboard_last(payload)
        if px is not None:
            out[sym] = px
    return out


def load_legacy_quote_prices(
    symbols: list[str],
    *,
    redis_url: str = REDIS_URL,
    quote_key: str = LEGACY_QUOTE_KEY,
    client: redis.Redis | None = None,
) -> dict[str, float]:
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
        keys = [quote_key.format(symbol=s) for s in symbols]
        raws = client.mget(keys)
    except (redis.exceptions.RedisError, OSError):
        return {}
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:
                pass
    out: dict[str, float] = {}
    for sym, raw in zip(symbols, raws or []):
        if not raw:
            continue
        try:
            data = json.loads(raw)
            px = float(data["price"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if px > 0:
            out[sym] = _desk_to_vnd(px)
    return out


def _read_ohlcv_rows(path: Path) -> list[dict[str, str]] | None:
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return None


def ohlcv_last_close_vnd(bars_dir: Path, symbol: str) -> float | None:
    rows = _read_ohlcv_rows(bars_dir / f"{symbol.strip().upper()}.csv")
    if not rows:
        return None
    for row in reversed(rows):
        raw = row.get("close")
        if raw is None or str(raw).strip() == "":
            continue
        try:
            close = float(raw)
        except (TypeError, ValueError):
            continue
        return _desk_to_vnd(close)
    return None


def ohlcv_avg_volume_10(bars_dir: Path, symbol: str, avg_bars: int = AVG_VOLUME_BARS) -> float | None:
    """TB volume avg_bars phiên trước nến cuối (parity volume_stats / wl_rows)."""
    rows = _read_ohlcv_rows(bars_dir / f"{symbol.strip().upper()}.csv")
    if not rows:
        return None
    volumes: list[float] = []
    for row in rows:
        raw = row.get("volume")
        if raw is None or str(raw).strip() == "":
            continue
        try:
            volumes.append(float(raw))
        except (TypeError, ValueError):
            continue
    need = avg_bars + 1
    if len(volumes) < need:
        return None
    prior = volumes[-(avg_bars + 1) : -1]
    if len(prior) < avg_bars:
        return None
    avg = sum(prior) / avg_bars
    return avg if avg > 0 else None


def resolve_portfolio_quotes(
    symbols: list[str],
    *,
    bars_dir: Path | None = None,
    priceboard: dict[str, float] | None = None,
    legacy: dict[str, float] | None = None,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Returns (quotes_by_symbol, priceboard_hits, priced_count)."""
    bars = bars_dir or DEFAULT_BARS_DIR
    pb = priceboard if priceboard is not None else load_priceboard_prices(symbols)
    quotes: dict[str, dict[str, Any]] = {}
    pb_hits = 0
    priced = 0
    need_legacy: list[str] = []
    for sym in symbols:
        price: float | None = None
        source: str | None = None
        live = pb.get(sym)
        if live is not None:
            price = live
            source = "priceboard"
            pb_hits += 1
            priced += 1
        else:
            fb = ohlcv_last_close_vnd(bars, sym)
            if fb is not None:
                price = fb
                source = "ohlcv"
                priced += 1
            else:
                need_legacy.append(sym)
        avg10 = ohlcv_avg_volume_10(bars, sym)
        quotes[sym] = {
            "price": price,
            "price_source": source,
            "avg_volume_10": avg10,
        }

    leg_map = legacy if legacy is not None else load_legacy_quote_prices(need_legacy)
    for sym in need_legacy:
        leg_px = leg_map.get(sym)
        if leg_px is None:
            continue
        quotes[sym]["price"] = leg_px
        quotes[sym]["price_source"] = "legacy_quote"
        priced += 1

    return quotes, pb_hits, priced
