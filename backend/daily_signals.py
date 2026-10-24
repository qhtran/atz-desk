"""Batch OHLCV filters for iBoard «Tín hiệu ngày» (subset, một bảng)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from backend.board_universe import symbols_for_market_tab
from backend.portfolio_f3 import _ensure_legacy_path, _legacy_atz_root, load_symbol_bars

ALLOWED_FILTERS = frozenset({"rsi", "macd", "ma"})


@lru_cache(maxsize=1)
def _filter_registry() -> dict[str, Any]:
    _ensure_legacy_path()
    root = _legacy_atz_root()
    filters_dir = root / "filters"
    if not filters_dir.is_dir():
        return {}
    from filters import load_registry

    reg = load_registry(filters_dir)
    return {k: v for k, v in reg.items() if k in ALLOWED_FILTERS}


def scan_daily_signals(
    *,
    market: str = "HOSE",
    filter_name: str = "rsi",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét mã; trả (hits, scanned, matched_count)."""
    name = str(filter_name or "rsi").strip().lower()
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
