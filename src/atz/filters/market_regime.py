"""VNINDEX trên/dưới MA dài (params.index_bars)."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import sma
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="market_regime",
    label="Regime VNINDEX",
    description="Chỉ match khi VNINDEX đóng cửa trên MA dài (uptrend).",
    group="xu hướng",
    params=(ParamSpec("ma_length", "int", C.MARKET_REGIME_MA, "MA VNINDEX", min=50, max=300),),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    raw = dict(params or {})
    index_bars = raw.get("index_bars")
    if index_bars is None or getattr(index_bars, "empty", True):
        return waiting("thiếu dữ liệu VNINDEX")
    close = pd.to_numeric(index_bars["close"], errors="coerce")
    ma_len = chosen["ma_length"]
    if len(close) < ma_len:
        return waiting()
    ma_line = sma(close, ma_len)
    if pd.isna(ma_line.iloc[-1]) or pd.isna(close.iloc[-1]):
        return waiting()
    last = float(close.iloc[-1])
    ma_val = float(ma_line.iloc[-1])
    details = {"close": round(last, 2), "ma": round(ma_val, 2), "ma_length": ma_len}
    if last > ma_val:
        return hit("mua", f"VNINDEX trên MA{ma_len}", details)
    if last < ma_val:
        return hit("ban", f"VNINDEX dưới MA{ma_len}", details)
    return hold("VNINDEX sát MA", details)
