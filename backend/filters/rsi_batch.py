"""Batch RSI: vectorized co_ban; f1 delegates to legacy evaluate (series core)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.filters._types import BatchSignal
from backend.portfolio_f3 import _ensure_legacy_path


def _legacy_rsi():
    _ensure_legacy_path()
    from filters.rsi import evaluate as legacy_evaluate
    from filters.rsi import FILTER

    return legacy_evaluate, FILTER


def _co_ban_batch(close: pd.DataFrame, chosen: dict[str, Any]) -> dict[str, BatchSignal]:
    _ensure_legacy_path()
    from analysis.technical import rsi as legacy_rsi_series

    length = int(chosen["length"])
    oversold = float(chosen["oversold"])
    overbought = float(chosen["overbought"])
    rsi_cols = close.apply(lambda series: legacy_rsi_series(series, length))
    last = rsi_cols.iloc[-1]
    out: dict[str, BatchSignal] = {}
    for code in close.columns:
        series = rsi_cols[code]
        bar_count = len(close[code].dropna())
        if bar_count <= length or series.empty or pd.isna(series.iloc[-1]):
            out[code] = BatchSignal(False, "giu", "không đủ dữ liệu", None)
            continue
        value = round(float(series.iloc[-1]), 2)
        details = {"rsi": value, "length": length}
        if value <= oversold:
            out[code] = BatchSignal(
                True,
                "mua",
                f"RSI {value} dưới {oversold}",
                details,
            )
        elif value >= overbought:
            out[code] = BatchSignal(
                True,
                "ban",
                f"RSI {value} trên {overbought}",
                details,
            )
        else:
            out[code] = BatchSignal(False, "giu", f"RSI {value}", details)
    return out


def _legacy_to_batch(result: Any) -> BatchSignal:
    matched = bool(getattr(result, "matched", False))
    signal_type = str(getattr(result, "signal_type", "giu") or "giu")
    reason = str(getattr(result, "reason", "") or "")
    details = getattr(result, "details", None)
    return BatchSignal(matched, signal_type, reason, details)


def evaluate_rsi_batch(
    panels: dict[str, pd.DataFrame],
    params: dict[str, Any] | None = None,
) -> dict[str, BatchSignal]:
    legacy_evaluate, FILTER = _legacy_rsi()
    _ensure_legacy_path()
    from filters.base import resolve_params

    chosen = resolve_params(FILTER, params)
    if params:
        for key, val in params.items():
            if key in chosen:
                chosen[key] = val

    cols: dict[str, pd.Series] = {}
    for sym, bars in panels.items():
        if bars is None or bars.empty or "close" not in bars.columns:
            continue
        code = str(sym).upper()
        cols[code] = pd.to_numeric(bars["close"], errors="coerce").reset_index(drop=True)

    if not cols:
        return {}

    if str(chosen.get("mode", "f1")) == "co_ban":
        return _co_ban_batch(pd.DataFrame(cols), chosen)

    out: dict[str, BatchSignal] = {}
    for sym, bars in panels.items():
        code = str(sym).upper()
        if code not in cols:
            continue
        try:
            res = legacy_evaluate(bars, chosen)
        except Exception:
            out[code] = BatchSignal(False, "giu", "không đủ dữ liệu", None)
            continue
        out[code] = _legacy_to_batch(res)
    return out
