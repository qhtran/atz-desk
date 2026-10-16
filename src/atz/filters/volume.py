"""Khối lượng phiên cuối so với trung bình, nến tăng hoặc giảm."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import sma
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="volume",
    label="Khối lượng đột biến",
    description="Khối lượng phiên cuối vượt trung bình và nến có hướng.",
    group="dòng tiền",
    params=(
        ParamSpec("length", "int", C.VOLUME_AVG, "Số phiên trung bình", min=2, max=100),
        ParamSpec("spike", "float", C.VOLUME_SPIKE, "Hệ số đột biến", min=1, max=10),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    open_ = pd.to_numeric(bars["open"], errors="coerce")
    average = sma(volume, chosen["length"])
    if pd.isna(average.iloc[-1]) or float(average.iloc[-1]) == 0:
        return waiting()
    ratio = float(volume.iloc[-1]) / float(average.iloc[-1])
    details = {"ratio": round(ratio, 2), "spike": chosen["spike"]}
    if ratio < chosen["spike"]:
        return hold(f"Khối lượng {details['ratio']} lần trung bình", details)
    if float(close.iloc[-1]) > float(open_.iloc[-1]):
        return hit("mua", f"Khối lượng đột biến {details['ratio']} lần, nến tăng", details)
    if float(close.iloc[-1]) < float(open_.iloc[-1]):
        return hit("ban", f"Khối lượng đột biến {details['ratio']} lần, nến giảm", details)
    return hold("Khối lượng đột biến nhưng nến không có hướng", details)
