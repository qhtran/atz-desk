"""Giá chạm dải Bollinger. Công thức ở analysis.technical.bollinger."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import bollinger
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="bollinger",
    label="Bollinger",
    description="Giá đóng cửa chạm hoặc vượt dải dưới hay dải trên.",
    group="dao động",
    params=(
        ParamSpec("length", "int", C.BB_LENGTH, "Số phiên", min=5, max=100),
        ParamSpec("k", "float", C.BB_STD, "Độ rộng", min=0.5, max=4),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    close = pd.to_numeric(bars["close"], errors="coerce")
    lower, _mid, upper = bollinger(close, chosen["length"], chosen["k"])
    if pd.isna(lower.iloc[-1]) or pd.isna(upper.iloc[-1]):
        return waiting()
    price = float(close.iloc[-1])
    low = float(lower.iloc[-1])
    up = float(upper.iloc[-1])
    details = {"close": price, "lower": round(low, 4), "upper": round(up, 4)}
    if low == up:
        return hold("dải Bollinger bằng nhau", details)
    if price <= low:
        return hit("mua", "Giá chạm dải Bollinger dưới", details)
    if price >= up:
        return hit("ban", "Giá chạm dải Bollinger trên", details)
    return hold("Giá nằm trong dải Bollinger", details)
