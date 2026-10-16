"""Chuỗi close ngắn cho sparkline bảng mã (OHLCV local, nghìn đồng)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import BARS_DIR, SPARKLINE_BARS, THOUSAND_VND
from engine.runner import load_symbol_csv


def closes_sparkline(bars: pd.DataFrame | None, *, n: int = SPARKLINE_BARS) -> list[float]:
    if bars is None or bars.empty or "close" not in bars.columns:
        return []
    close = pd.to_numeric(bars["close"], errors="coerce").dropna()
    if close.empty:
        return []
    return [float(v) for v in close.tail(n).tolist()]


def load_sparkline(
    symbol: str,
    *,
    bars_dir: Path | None = None,
    n: int = SPARKLINE_BARS,
    live_price_vnd: float | None = None,
) -> list[float]:
    root = bars_dir if bars_dir is not None else BARS_DIR
    code = symbol.strip().upper()
    try:
        frame = load_symbol_csv(root, code)
    except Exception:
        frame = None
    series = closes_sparkline(frame, n=n)
    if live_price_vnd is not None and live_price_vnd > 0:
        live_k = live_price_vnd / THOUSAND_VND
        if not series or abs(series[-1] - live_k) > 1e-6:
            series = series + [live_k]
    return series


def load_sparklines(
    symbols: list[str],
    *,
    bars_dir: Path | None = None,
    n: int = SPARKLINE_BARS,
    live_prices_vnd: dict[str, float] | None = None,
) -> dict[str, list[float]]:
    live = live_prices_vnd or {}
    return {
        code: load_sparkline(code, bars_dir=bars_dir, n=n, live_price_vnd=live.get(code))
        for code in (s.strip().upper() for s in symbols if str(s).strip())
    }
