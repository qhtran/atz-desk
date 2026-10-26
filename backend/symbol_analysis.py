"""Chart bars + lịch sử marker filter theo mã (iBoard symbol detail)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from backend.daily_signals import (
    ALLOWED_FILTERS,
    _advisor_hit,
    _filter_registry,
    _plugin_params,
)
from backend.portfolio_f3 import load_symbol_bars

_CHART_COLS = ("time", "open", "high", "low", "close", "volume")


def load_bars_for_chart(
    symbol: str,
    *,
    limit: int = 252,
    bars_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """OHLCV daily cho chart (JSON-safe)."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        return []
    frame = load_symbol_bars(sym, bars_dir)
    if frame is None or frame.empty:
        return []
    tail = frame.tail(max(1, min(int(limit), 500)))
    out: list[dict[str, Any]] = []
    for _, row in tail.iterrows():
        rec: dict[str, Any] = {}
        for col in _CHART_COLS:
            if col not in tail.columns:
                continue
            val = row[col]
            if pd.isna(val):
                continue
            if col == "time":
                rec[col] = str(val)
            else:
                rec[col] = float(val)
        if "close" in rec:
            out.append(rec)
    return out


def _index_bars_if_needed(filter_name: str, bars_dir: Path | None) -> pd.DataFrame | None:
    if filter_name in {"rs_index", "market_regime"}:
        return load_symbol_bars("VNINDEX", bars_dir)
    return None


def _time_key(frame: pd.DataFrame, index: int) -> str:
    if "time" in frame.columns:
        return str(frame["time"].iloc[index])
    return str(index)


def scan_filter_markers(
    symbol: str,
    filter_name: str,
    *,
    limit: int = 252,
    bars_dir: Path | None = None,
    buy_min_total: float | None = None,
) -> dict[str, Any]:
    """Rolling evaluate: marker tại cạnh matched (False → True)."""
    sym = str(symbol or "").strip().upper()
    name = str(filter_name or "").strip().lower()
    base: dict[str, Any] = {"ok": True, "symbol": sym, "filter": name, "bars": [], "markers": [], "last": None}
    if not sym or name not in ALLOWED_FILTERS:
        base["ok"] = False
        base["error"] = "filter_or_symbol_invalid"
        return base

    bars = load_symbol_bars(sym, bars_dir)
    if bars is None or bars.empty:
        base["ok"] = False
        base["error"] = "no_bars"
        return base

    bars = bars.tail(max(1, min(int(limit), 500))).reset_index(drop=True)
    base["bars"] = load_bars_for_chart(sym, limit=limit, bars_dir=bars_dir)

    if name == "advisor":
        ok, extra = _advisor_hit(bars, buy_min_total)
        base["last"] = {
            "matched": ok,
            "history": False,
            "reason": extra.get("reason", "Cố vấn không có marker lịch sử trên chart") if extra else "không đủ dữ liệu",
            **(extra or {}),
        }
        base["markers"] = []
        return base

    registry = _filter_registry()
    module = registry.get(name)
    if module is None:
        base["ok"] = False
        base["error"] = "filter_not_loaded"
        return base

    index_bars = _index_bars_if_needed(name, bars_dir)
    params = _plugin_params(name, index_bars)
    evaluate = module.evaluate
    markers: list[dict[str, Any]] = []
    prev_matched = False
    start = max(5, min(30, len(bars) // 4))

    for i in range(start, len(bars)):
        slice_df = bars.iloc[: i + 1]
        try:
            result = evaluate(slice_df, params)
        except Exception:
            prev_matched = False
            continue
        matched = bool(getattr(result, "matched", False))
        if matched and not prev_matched:
            markers.append(
                {
                    "time": _time_key(bars, i),
                    "signal_type": getattr(result, "signal_type", ""),
                    "reason": getattr(result, "reason", ""),
                }
            )
        prev_matched = matched

    try:
        last_result = evaluate(bars, params)
    except Exception:
        last_result = None

    if last_result is not None:
        base["last"] = {
            "matched": bool(getattr(last_result, "matched", False)),
            "signal_type": getattr(last_result, "signal_type", ""),
            "reason": getattr(last_result, "reason", ""),
            "history": True,
        }
    base["markers"] = markers
    return base
