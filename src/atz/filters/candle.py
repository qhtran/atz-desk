"""Mẫu nến phiên cuối. Nhận diện nằm ở analysis.candles.

mode "f1" (mặc định, F1 mục 7 hàng 1): chỉ báo mua khi nến đảo chiều tăng
(Engulfing tăng / Hammer) chạm vùng hỗ trợ. mode "co_ban": mọi mẫu nến đơn như trước.
"""

from __future__ import annotations

import pandas as pd

from analysis.candles import candle_pattern, reversal_at_support
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="candle",
    label="Nến đơn",
    description="F1: nến đảo chiều tăng (Engulfing tăng / Hammer) tại vùng hỗ trợ. Cơ bản: mọi mẫu nến đơn.",
    group="nến",
    params=(ParamSpec("mode", "choice", "f1", "Chế độ", choices=("f1", "co_ban")),),
)

_SIDE = {
    "Engulfing tăng": "mua",
    "Hammer": "mua",
    "Engulfing giảm": "ban",
    "Shooting Star": "ban",
}

_COLUMNS = ("open", "high", "low", "close")


def _classic(bars: pd.DataFrame) -> SignalResult:
    name = candle_pattern(bars)
    if name in _SIDE:
        return hit(_SIDE[name], name or "", {"pattern": name})
    if name == "Doji":
        return SignalResult(False, "cho", None, "Doji", {"pattern": "Doji"})
    return waiting("không có mẫu nến")


def _f1(bars: pd.DataFrame) -> SignalResult:
    try:
        scan = reversal_at_support(bars)
    except (KeyError, ValueError, TypeError) as error:
        return waiting(f"không đủ dữ liệu hỗ trợ: {error}")
    details = {key: scan[key] for key in ("pattern", "at_support", "support", "zone_top", "support_tests")}
    if scan["bullish"] and scan["at_support"]:
        return hit("mua", f"{scan['pattern']} tại hỗ trợ {scan['support']}", details)
    if scan["bullish"]:
        return hold(f"{scan['pattern']} nhưng chưa chạm hỗ trợ", details)
    return hold("không có nến đảo chiều tăng", details)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    missing = [column for column in _COLUMNS if column not in bars.columns]
    if missing:
        return waiting(f"không đủ dữ liệu: thiếu cột {', '.join(missing)}")
    if len(bars) < 2:
        return waiting()
    if chosen["mode"] == "co_ban":
        return _classic(bars)
    return _f1(bars)
