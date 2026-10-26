"""Đóng cửa phá đỉnh 52 tuần (lookback phiên)."""

from __future__ import annotations

import pandas as pd

import config as C
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="breakout_52w",
    label="Breakout 52 tuần",
    description="Giá đóng cửa vượt đỉnh cao nhất lookback phiên (mặc định 252).",
    group="xu hướng",
    params=(ParamSpec("lookback", "int", C.BREAKOUT_LOOKBACK, "Số phiên", min=60, max=300),),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    lookback = chosen["lookback"]
    if len(bars) < lookback:
        return waiting()
    high = pd.to_numeric(bars["high"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    window = high.iloc[-lookback:-1]
    if window.isna().any() or pd.isna(close.iloc[-1]) or pd.isna(close.iloc[-2]):
        return waiting()
    prior_peak = float(window.max())
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    details = {"prior_high": round(prior_peak, 4), "close": round(last, 4)}
    if last >= prior_peak and prev < prior_peak:
        return hit("mua", f"Phá đỉnh {lookback} phiên", details)
    if last >= prior_peak:
        return hold("Đã trên đỉnh lookback", details)
    return hold("Chưa phá đỉnh lookback", details)
