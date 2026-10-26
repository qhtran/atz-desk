"""Chuỗi phiên khối ngoại mua/bán ròng (N ngày liên tiếp)."""

from __future__ import annotations

import pandas as pd

import config as C
from filters._net import evaluate_net
from filters.base import FilterSpec, ParamSpec, SignalResult

FILTER = FilterSpec(
    name="foreign_streak",
    label="KN streak",
    description="Khối ngoại mua ròng hoặc bán ròng liên tiếp ≥ N phiên.",
    group="dòng tiền",
    params=(
        ParamSpec("days", "int", C.FOREIGN_STREAK_DAYS, "Số phiên liên tiếp", min=2, max=20),
        ParamSpec("min_net_vol", "float", 0.0, "KL ròng tối thiểu", min=0, max=1_000_000_000),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    return evaluate_net(FILTER, bars, params, "foreign_net_vol", "Khối ngoại")
