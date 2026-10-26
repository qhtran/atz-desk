"""ATR phiên cuối vượt trung bình và nến có hướng."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import atr, sma
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="atr",
    label="ATR đột biến",
    description="Biên độ (ATR) vượt trung bình và nến tăng/giảm.",
    group="dao động",
    params=(
        ParamSpec("length", "int", C.ATR_LENGTH, "Chu kỳ ATR", min=5, max=50),
        ParamSpec("avg_length", "int", C.ATR_AVG, "TB ATR", min=5, max=100),
        ParamSpec("spike", "float", C.ATR_SPIKE, "Hệ số đột biến", min=1, max=5),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    length, avg_len = chosen["length"], chosen["avg_length"]
    need = length + avg_len + 1
    if len(bars) < need:
        return waiting()
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    open_ = pd.to_numeric(bars["open"], errors="coerce")
    atr_line = atr(high, low, close, length)
    average = sma(atr_line, avg_len)
    if pd.isna(atr_line.iloc[-1]) or pd.isna(average.iloc[-1]) or float(average.iloc[-1]) == 0:
        return waiting()
    ratio = float(atr_line.iloc[-1]) / float(average.iloc[-1])
    details = {"atr_ratio": round(ratio, 2), "spike": chosen["spike"]}
    if ratio < chosen["spike"]:
        return hold(f"ATR {details['atr_ratio']} lần trung bình", details)
    if float(close.iloc[-1]) > float(open_.iloc[-1]):
        return hit("mua", f"ATR đột biến {details['atr_ratio']} lần, nến tăng", details)
    if float(close.iloc[-1]) < float(open_.iloc[-1]):
        return hit("ban", f"ATR đột biến {details['atr_ratio']} lần, nến giảm", details)
    return hold("ATR đột biến nhưng nến không có hướng", details)
