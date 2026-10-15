"""Khối ngoại mua hoặc bán ròng. Số liệu đến từ cột foreign_net_vol."""

from __future__ import annotations

import pandas as pd

from filters._net import evaluate_net
from filters.base import FilterSpec, ParamSpec, SignalResult

FILTER = FilterSpec(
    name="foreign",
    label="Khối ngoại",
    description="Khối ngoại mua ròng hoặc bán ròng trên các phiên cuối.",
    group="dòng tiền",
    params=(
        ParamSpec("days", "int", 1, "Số phiên liên tiếp", min=1, max=20),
        ParamSpec("min_net_vol", "float", 0.0, "Khối lượng ròng tối thiểu", min=0, max=1_000_000_000),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    return evaluate_net(FILTER, bars, params, "foreign_net_vol", "Khối ngoại")
