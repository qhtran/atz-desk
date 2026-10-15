"""Tự doanh mua hoặc bán ròng. Số liệu đến từ cột prop_net_vol."""

from __future__ import annotations

import pandas as pd

from filters._net import evaluate_net
from filters.base import FilterSpec, ParamSpec, SignalResult

FILTER = FilterSpec(
    name="proprietary",
    label="Tự doanh",
    description="Tự doanh mua ròng hoặc bán ròng trên các phiên cuối.",
    group="dòng tiền",
    params=(
        ParamSpec("days", "int", 1, "Số phiên liên tiếp", min=1, max=20),
        ParamSpec("min_net_vol", "float", 0.0, "Khối lượng ròng tối thiểu", min=0, max=1_000_000_000),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    return evaluate_net(FILTER, bars, params, "prop_net_vol", "Tự doanh")
