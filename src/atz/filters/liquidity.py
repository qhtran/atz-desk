"""Thanh khoản: KL và GT trung bình vượt ngưỡng."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import sma
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting


def _gt_series(bars: pd.DataFrame) -> pd.Series:
    if "gtgd" in bars.columns:
        return pd.to_numeric(bars["gtgd"], errors="coerce")
    if "value" in bars.columns:
        return pd.to_numeric(bars["value"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    return close * volume


FILTER = FilterSpec(
    name="liquidity",
    label="Thanh khoản",
    description="KL và giá trị giao dịch trung bình ≥ ngưỡng.",
    group="dòng tiền",
    params=(
        ParamSpec("length", "int", C.LIQUIDITY_AVG, "Số phiên TB", min=5, max=60),
        ParamSpec("min_vol", "float", C.LIQUIDITY_MIN_VOL, "KL TB tối thiểu", min=0, max=1_000_000_000),
        ParamSpec("min_gt", "float", C.LIQUIDITY_MIN_GT, "GT TB tối thiểu", min=0, max=1e15),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    length = chosen["length"]
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    gt = _gt_series(bars)
    if len(volume) < length or volume.iloc[-length:].isna().any() or gt.iloc[-length:].isna().any():
        return waiting()
    avg_vol = float(sma(volume, length).iloc[-1])
    avg_gt = float(sma(gt, length).iloc[-1])
    details = {
        "avg_vol": round(avg_vol, 0),
        "avg_gt": round(avg_gt, 0),
        "min_vol": chosen["min_vol"],
        "min_gt": chosen["min_gt"],
    }
    if avg_vol >= chosen["min_vol"] and avg_gt >= chosen["min_gt"]:
        return hit("mua", "Thanh khoản đủ lớn", details)
    return hold("Thanh khoản dưới ngưỡng", details)
