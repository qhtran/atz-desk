"""Mẫu nến phiên cuối. Nhận diện nằm ở analysis.candles."""

from __future__ import annotations

import pandas as pd

from analysis.candles import candle_pattern
from filters.base import FilterSpec, SignalResult, hit, waiting

FILTER = FilterSpec(
    name="candle",
    label="Nến đơn",
    description="Engulfing, Hammer hoặc Shooting Star của phiên cuối.",
    group="nến",
    params=(),
)

_SIDE = {
    "Engulfing tăng": "mua",
    "Hammer": "mua",
    "Engulfing giảm": "ban",
    "Shooting Star": "ban",
}


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    del params
    if len(bars) < 2:
        return waiting()
    name = candle_pattern(bars)
    if name in _SIDE:
        return hit(_SIDE[name], name or "", {"pattern": name})
    if name == "Doji":
        return SignalResult(False, "cho", None, "Doji", {"pattern": "Doji"})
    return waiting("không có mẫu nến")
