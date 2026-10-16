"""So net_vol các phiên cuối. Hai filter khối ngoại và tự doanh dùng chung."""

from __future__ import annotations

import pandas as pd

from filters.base import SignalResult, hit, hold, resolve_params, waiting


def evaluate_net(spec, bars: pd.DataFrame, params: dict | None, column: str, label: str) -> SignalResult:
    chosen = resolve_params(spec, params)
    if column not in bars.columns:
        return waiting()
    series = pd.to_numeric(bars[column], errors="coerce")
    days = chosen["days"]
    if series.iloc[-days:].isna().any():
        return waiting()
    tail = series.iloc[-days:]
    floor = float(chosen["min_net_vol"])
    last = float(tail.iloc[-1])
    details = {"net_vol": last, "days": days}
    if (tail > floor).all():
        return hit("mua", f"{label} mua ròng {days} phiên", details)
    if (tail < -floor).all():
        return hit("ban", f"{label} bán ròng {days} phiên", details)
    return hold(f"{label} chưa lệch đủ", details)
