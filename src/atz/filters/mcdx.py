"""MCDX: Banker cắt qua mốc 0. Công thức ở analysis.technical.mcdx."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import mcdx
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="mcdx",
    label="MCDX",
    description="Banker cắt lên trên 0 khi sức mạnh tăng, cắt xuống dưới 0 khi yếu đi.",
    group="dòng tiền",
    params=(
        ParamSpec("banker_period", "int", C.MCDX_BANKER_PERIOD, "Chu kỳ Banker", min=2, max=100),
        ParamSpec("banker_base", "float", C.MCDX_BANKER_BASE, "Mốc RSI Banker", min=1, max=99),
        ParamSpec("banker_sens", "float", C.MCDX_BANKER_SENS, "Hệ số Banker", min=0.1, max=5),
        ParamSpec("hot_period", "int", C.MCDX_HOT_PERIOD, "Chu kỳ Hot Money", min=2, max=100),
        ParamSpec("hot_base", "float", C.MCDX_HOT_BASE, "Mốc RSI Hot Money", min=1, max=99),
        ParamSpec("hot_sens", "float", C.MCDX_HOT_SENS, "Hệ số Hot Money", min=0.1, max=5),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    close = pd.to_numeric(bars["close"], errors="coerce")
    banker, hot, banker_raw = mcdx(
        close,
        chosen["banker_period"],
        chosen["banker_base"],
        chosen["banker_sens"],
        chosen["hot_period"],
        chosen["hot_base"],
        chosen["hot_sens"],
    )
    tail = banker_raw.iloc[-2:]
    if len(tail) < 2 or tail.isna().any():
        return waiting()
    previous, current = float(tail.iloc[0]), float(tail.iloc[1])
    hot_now = hot.iloc[-1]
    details = {
        "banker": round(float(banker.iloc[-1]), 2),
        "hot": None if pd.isna(hot_now) else round(float(hot_now), 2),
        "banker_raw": round(current, 4),
    }
    if previous <= 0 < current:
        return hit("mua", "Banker cắt lên, sức mạnh tăng", details)
    if previous >= 0 > current:
        return hit("ban", "Banker cắt xuống, sức mạnh yếu đi", details)
    return hold("MCDX chưa cắt", details)
