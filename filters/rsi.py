"""RSI Wilder qua analysis.technical.rsi."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import rsi
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="rsi",
    label="RSI",
    description="RSI phiên cuối dưới vùng bán hoặc trên vùng mua.",
    group="dao động",
    params=(
        ParamSpec("length", "int", C.RSI_LENGTH, "Số phiên", min=2, max=100),
        ParamSpec("oversold", "float", float(C.RSI_OVERSOLD), "Ngưỡng mua", min=1, max=50),
        ParamSpec("overbought", "float", float(C.RSI_OVERBOUGHT), "Ngưỡng bán", min=50, max=99),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    close = pd.to_numeric(bars["close"], errors="coerce")
    series = rsi(close, chosen["length"])
    value = series.iloc[-1]
    if len(close) <= chosen["length"] or pd.isna(value):
        return waiting()
    details = {"rsi": round(float(value), 2), "length": chosen["length"]}
    if value <= chosen["oversold"]:
        return hit("mua", f"RSI {details['rsi']} dưới {chosen['oversold']}", details)
    if value >= chosen["overbought"]:
        return hit("ban", f"RSI {details['rsi']} trên {chosen['overbought']}", details)
    return hold(f"RSI {details['rsi']}", details)
