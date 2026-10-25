"""Batch OHLCV filters for iBoard «Tín hiệu ngày» (subset, một bảng)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from backend.board_universe import symbols_for_market_tab
from backend.portfolio_f3 import _ensure_legacy_path, _legacy_atz_root, load_symbol_bars

ALLOWED_FILTERS = frozenset({"rsi", "macd", "ma", "advisor"})


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
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét mã; trả (hits, scanned, matched_count)."""
    name = str(filter_name or "rsi").strip().lower()
    if name == "advisor":
        return scan_advisor_scores(
            market=market,
            symbols=symbols,
            bars_dir=bars_dir,
            buy_min_total=buy_min_total,
        )
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
    return hits, scanned, len(hits)


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
