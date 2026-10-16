"""MACD cắt đường tín hiệu, dùng analysis.technical.macd."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import macd
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="macd",
    label="MACD",
    description="Histogram MACD cắt lên hoặc cắt xuống mốc 0 ở phiên cuối.",
    group="dao động",
    params=(
        ParamSpec("fast", "int", C.MACD_FAST, "EMA nhanh", min=2, max=50),
        ParamSpec("slow", "int", C.MACD_SLOW, "EMA chậm", min=3, max=100),
        ParamSpec("signal", "int", C.MACD_SIGNAL, "Đường tín hiệu", min=2, max=50),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    if chosen["fast"] >= chosen["slow"]:
        return waiting("EMA nhanh phải nhỏ hơn EMA chậm")
    close = pd.to_numeric(bars["close"], errors="coerce")
    _line, _signal, hist = macd(close, chosen["fast"], chosen["slow"], chosen["signal"])
    tail = hist.iloc[-2:]
    if tail.isna().any():
        return waiting()
    details = {"histogram": round(float(hist.iloc[-1]), 4)}
    if hist.iloc[-2] <= 0 < hist.iloc[-1]:
        return hit("mua", "MACD cắt lên", details)
    if hist.iloc[-2] >= 0 > hist.iloc[-1]:
        return hit("ban", "MACD cắt xuống", details)
    return hold("MACD chưa cắt", details)
