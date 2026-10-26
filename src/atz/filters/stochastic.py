"""Stochastic %K cắt %D."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import stochastic
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="stochastic",
    label="Stochastic",
    description="%K cắt lên %D từ vùng oversold hoặc cắt xuống từ overbought.",
    group="dao động",
    params=(
        ParamSpec("k", "int", C.STOCH_K, "%K", min=5, max=50),
        ParamSpec("d", "int", C.STOCH_D, "%D", min=2, max=20),
        ParamSpec("oversold", "int", C.STOCH_OVERSOLD, "Oversold", min=5, max=40),
        ParamSpec("overbought", "int", C.STOCH_OVERBOUGHT, "Overbought", min=60, max=95),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    k_line, d_line = stochastic(high, low, close, chosen["k"], chosen["d"])
    tail_k = k_line.iloc[-2:]
    tail_d = d_line.iloc[-2:]
    if len(tail_k) < 2 or tail_k.isna().any() or tail_d.isna().any():
        return waiting()
    k0, k1 = float(k_line.iloc[-2]), float(k_line.iloc[-1])
    d0, d1 = float(d_line.iloc[-2]), float(d_line.iloc[-1])
    details = {"k": round(k1, 2), "d": round(d1, 2)}
    crossed_up = k0 <= d0 and k1 > d1 and k1 <= chosen["overbought"]
    crossed_down = k0 >= d0 and k1 < d1 and k1 >= chosen["oversold"]
    if crossed_up and k0 <= chosen["oversold"] + 15:
        return hit("mua", "%K cắt lên %D", details)
    if crossed_down and k0 >= chosen["overbought"] - 15:
        return hit("ban", "%K cắt xuống %D", details)
    return hold("Stochastic chưa cắt", details)
