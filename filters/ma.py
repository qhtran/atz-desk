"""Cắt đường trung bình. Công thức SMA nằm ở analysis.technical."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import sma
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="ma",
    label="Cắt đường trung bình",
    description="MA nhanh cắt MA chậm trên phiên cuối.",
    group="xu hướng",
    params=(
        ParamSpec("fast", "int", C.MA_SHORT, "MA nhanh", min=2, max=100),
        ParamSpec("slow", "int", C.MA_MID, "MA chậm", min=3, max=300),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    fast, slow = chosen["fast"], chosen["slow"]
    if fast >= slow:
        return waiting("MA nhanh phải nhỏ hơn MA chậm")
    close = pd.to_numeric(bars["close"], errors="coerce")
    fast_ma = sma(close, fast)
    slow_ma = sma(close, slow)
    tail_fast = fast_ma.iloc[-2:]
    tail_slow = slow_ma.iloc[-2:]
    if len(close) < slow + 1 or tail_fast.isna().any() or tail_slow.isna().any():
        return waiting()
    crossed_up = fast_ma.iloc[-2] <= slow_ma.iloc[-2] and fast_ma.iloc[-1] > slow_ma.iloc[-1]
    crossed_down = fast_ma.iloc[-2] >= slow_ma.iloc[-2] and fast_ma.iloc[-1] < slow_ma.iloc[-1]
    details = {
        "fast": float(fast_ma.iloc[-1]),
        "slow": float(slow_ma.iloc[-1]),
        "fast_length": fast,
        "slow_length": slow,
    }
    if crossed_up:
        return hit("mua", f"MA{fast} cắt lên MA{slow}", details)
    if crossed_down:
        return hit("ban", f"MA{fast} cắt xuống MA{slow}", details)
    return hold("chưa cắt MA", details)
