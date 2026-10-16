"""MACD cắt đường tín hiệu, dùng analysis.technical.macd.

mode "f1" (mặc định, F1 mục 7 hàng 3): mua khi MACD cắt lên Signal trong cross_window
phiên gần nhất và histogram tăng liên tiếp >= improve_bars phiên (analysis.technical.macd_improving).
mode "co_ban": histogram cắt mốc 0 ở phiên cuối như trước.
"""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import macd, macd_improving
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="macd",
    label="MACD",
    description="F1: MACD cắt lên Signal + histogram cải thiện ≥ 2 phiên. Cơ bản: histogram cắt mốc 0 ở phiên cuối.",
    group="dao động",
    params=(
        ParamSpec("mode", "choice", "f1", "Chế độ", choices=("f1", "co_ban")),
        ParamSpec("fast", "int", C.MACD_FAST, "EMA nhanh", min=2, max=50),
        ParamSpec("slow", "int", C.MACD_SLOW, "EMA chậm", min=3, max=100),
        ParamSpec("signal", "int", C.MACD_SIGNAL, "Đường tín hiệu", min=2, max=50),
        ParamSpec("improve_bars", "int", 2, "F1: số phiên histogram tăng", min=2, max=10),
        ParamSpec("cross_window", "int", 3, "F1: cắt lên trong N phiên", min=1, max=10),
    ),
)


def _f1(line: pd.Series, sig: pd.Series, hist: pd.Series, chosen: dict) -> SignalResult:
    try:
        scan = macd_improving(line, sig, hist, chosen["cross_window"], chosen["improve_bars"])
    except ValueError as error:
        return waiting(f"không đủ dữ liệu: {error}")
    details = {"histogram": scan["histogram"], "cross_ago": scan["cross_ago"], "improving": scan["improving"]}
    if scan["cross_ago"] is not None and scan["improving"]:
        return hit("mua", f"MACD cắt lên Signal ({scan['cross_ago']} phiên trước), histogram tăng {chosen['improve_bars']} phiên", details)
    if scan["cross_ago"] is not None:
        return hold(f"MACD cắt lên nhưng histogram chưa tăng {chosen['improve_bars']} phiên", details)
    if scan["above"]:
        return hold(f"MACD đã trên Signal hơn {chosen['cross_window']} phiên, không phải điểm cắt mới", details)
    return hold("MACD chưa cắt lên Signal", details)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    if chosen["fast"] >= chosen["slow"]:
        return waiting("EMA nhanh phải nhỏ hơn EMA chậm")
    if "close" not in bars.columns:
        return waiting("không đủ dữ liệu: thiếu cột close")
    close = pd.to_numeric(bars["close"], errors="coerce")
    line, sig, hist = macd(close, chosen["fast"], chosen["slow"], chosen["signal"])
    tail = hist.iloc[-2:]
    if len(tail) < 2 or tail.isna().any():
        return waiting()
    if chosen["mode"] == "f1":
        return _f1(line, sig, hist, chosen)
    details = {"histogram": round(float(hist.iloc[-1]), 4)}
    if hist.iloc[-2] <= 0 < hist.iloc[-1]:
        return hit("mua", "MACD cắt lên", details)
    if hist.iloc[-2] >= 0 > hist.iloc[-1]:
        return hit("ban", "MACD cắt xuống", details)
    return hold("MACD chưa cắt", details)
