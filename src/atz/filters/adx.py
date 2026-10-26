"""+DI > -DI khi ADX đủ mạnh (xu hướng). Công thức ở analysis.technical.adx."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import adx
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="adx",
    label="ADX",
    description="+DI trên -DI (hoặc ngược lại) và ADX ≥ ngưỡng xu hướng mạnh.",
    group="xu hướng",
    params=(
        ParamSpec("length", "int", C.ADX_LENGTH, "Chu kỳ ADX", min=5, max=50),
        ParamSpec("min_adx", "float", C.ADX_MIN, "ADX tối thiểu", min=10, max=60),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    length = chosen["length"]
    need = length * 2 + 2
    if len(bars) < need:
        return waiting()
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    adx_line, plus_di, minus_di = adx(high, low, close, length)
    if pd.isna(adx_line.iloc[-1]) or pd.isna(plus_di.iloc[-1]) or pd.isna(minus_di.iloc[-1]):
        return waiting()
    adx_val = float(adx_line.iloc[-1])
    plus_val = float(plus_di.iloc[-1])
    minus_val = float(minus_di.iloc[-1])
    details = {
        "adx": round(adx_val, 2),
        "plus_di": round(plus_val, 2),
        "minus_di": round(minus_val, 2),
        "min_adx": chosen["min_adx"],
    }
    if adx_val < chosen["min_adx"]:
        return hold(f"ADX {details['adx']} dưới ngưỡng {chosen['min_adx']}", details)
    if plus_val > minus_val:
        return hit("mua", "+DI trên -DI, ADX đủ mạnh", details)
    if minus_val > plus_val:
        return hit("ban", "-DI trên +DI, ADX đủ mạnh", details)
    return hold("DI cân bằng", details)
