"""Batch OHLCV filters for iBoard «Tín hiệu ngày» (subset, một bảng)."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from backend.board_universe import symbols_for_market_tab
from backend.portfolio_f3 import _ensure_legacy_path, _legacy_atz_root, load_symbol_bars

ALLOWED_FILTERS = frozenset({"rsi", "macd", "ma", "candle", "volume", "foreign", "advisor"})

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_scan_cache: dict[tuple[Any, ...], tuple[str, list[dict[str, Any]], int, int]] = {}


def _trading_day_key() -> str:
    return datetime.now(_VN_TZ).strftime("%Y-%m-%d")


def clear_daily_scan_cache() -> None:
    """Xóa cache quét (dùng trong test / sau cập nhật OHLCV)."""
    _scan_cache.clear()


@lru_cache(maxsize=1)
def _filter_registry() -> dict[str, Any]:
    _ensure_legacy_path()
    root = _legacy_atz_root()
    filters_dir = root / "filters"
    if not filters_dir.is_dir():
        return {}
    from filters import load_registry

    reg = load_registry(filters_dir)
    plugin_filters = ALLOWED_FILTERS - {"advisor"}
    return {k: v for k, v in reg.items() if k in plugin_filters}


@lru_cache(maxsize=1)
def _advisor_engine():
    _ensure_legacy_path()
    from engine.advisor_score import compute_advisor_score, load_advisor_config

    return compute_advisor_score, load_advisor_config


def scan_advisor_scores(
    *,
    market: str = "HOSE",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    buy_min_total: float | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét cố vấn 0–100; hits có total >= ngưỡng, sắp theo điểm giảm dần."""
    compute, load_cfg = _advisor_engine()
    cfg = load_cfg()
    th = cfg["thresholds"]
    floor = float(buy_min_total if buy_min_total is not None else th["buy_min_total"])
    params = {
        "thresholds": {
            "buy_min_total": floor,
            "sell_max_total": float(th["sell_max_total"]),
        },
    }
    universe = symbols or symbols_for_market_tab(market)
    hits: list[dict[str, Any]] = []
    scanned = 0
    for sym in universe:
        bars = load_symbol_bars(sym, bars_dir)
        if bars is None or bars.empty:
            continue
        scanned += 1
        try:
            score = compute(bars, params)
        except Exception:
            continue
        if score.total is None or float(score.total) < floor:
            continue
        hits.append(
            {
                "symbol": sym.upper(),
                "filter": "advisor",
                "signal_type": score.recommendation,
                "reason": score.reason,
                "total": score.total,
                "trend": score.pillars["trend"]["points"],
                "flow": score.pillars["flow"]["points"],
                "short_term": score.pillars["short_term"]["points"],
            }
        )
    hits.sort(key=lambda row: float(row["total"]), reverse=True)
    return hits, scanned, len(hits)


def scan_daily_signals(
    *,
    market: str = "HOSE",
    filter_name: str = "rsi",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    buy_min_total: float | None = None,
    use_cache: bool = True,
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét mã; trả (hits, scanned, matched_count)."""
    name = str(filter_name or "rsi").strip().lower()
    day = _trading_day_key()
    sym_key: tuple[str, ...] | None = None
    if symbols is not None:
        sym_key = tuple(sorted(str(s).upper() for s in symbols))
    cache_key = (market.upper(), name, buy_min_total, sym_key)
    if use_cache:
        cached = _scan_cache.get(cache_key)
        if cached and cached[0] == day:
            hits, scanned, matched = cached[1], cached[2], cached[3]
            return list(hits), scanned, matched

    if name == "advisor":
        hits, scanned, matched = scan_advisor_scores(
            market=market,
            symbols=symbols,
            bars_dir=bars_dir,
            buy_min_total=buy_min_total,
        )
        if use_cache:
            _scan_cache[cache_key] = (day, hits, scanned, matched)
        return hits, scanned, matched
    registry = _filter_registry()
    module = registry.get(name)
    if module is None:
        return [], 0, 0

    evaluate = module.evaluate
    universe = symbols or symbols_for_market_tab(market)
    hits: list[dict[str, Any]] = []
    scanned = 0
    for sym in universe:
        bars = load_symbol_bars(sym, bars_dir)
        if bars is None or bars.empty:
            continue
        scanned += 1
        try:
            result = evaluate(bars, None)
        except Exception:
            continue
        if not getattr(result, "matched", False):
            continue
        hits.append(
            {
                "symbol": sym.upper(),
                "filter": name,
                "signal_type": getattr(result, "signal_type", ""),
                "reason": getattr(result, "reason", ""),
            }
        )
    matched = len(hits)
    if use_cache:
        _scan_cache[cache_key] = (day, hits, scanned, matched)
    return hits, scanned, matched


def hit_symbols(
    *,
    market: str = "HOSE",
    filter_name: str = "rsi",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
) -> set[str]:
    rows, _, _ = scan_daily_signals(
        market=market,
        filter_name=filter_name,
        symbols=symbols,
        bars_dir=bars_dir,
    )
    return {str(r["symbol"]).upper() for r in rows}
