"""RS cổ phiếu so VNINDEX (params.index_bars do scanner inject)."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import rs_vs_index
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="rs_index",
    label="RS vs VNINDEX",
    description="Tăng % cổ phiếu vượt VNINDEX trong cửa sổ lookback.",
    group="xu hướng",
    params=(
        ParamSpec("lookback", "int", C.RS_INDEX_LOOKBACK, "Số phiên", min=20, max=120),
        ParamSpec("min_edge", "float", C.RS_INDEX_MIN_EDGE, "Vượt index (%)", min=-50, max=50),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    raw = dict(params or {})
    index_bars = raw.get("index_bars")
    if index_bars is None or getattr(index_bars, "empty", True):
        return waiting("thiếu dữ liệu VNINDEX")
    edge = rs_vs_index(bars, index_bars, chosen["lookback"])
    if edge is None:
        return waiting()
    details = {"rs_edge_pct": edge, "min_edge": chosen["min_edge"]}
    if edge >= chosen["min_edge"]:
        return hit("mua", f"RS vượt VNINDEX {edge}%", details)
    return hold(f"RS chưa vượt index ({edge}%)", details)
