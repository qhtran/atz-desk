"""Khối ngoại và tự doanh trên cột net_vol. Không gọi mạng."""

from __future__ import annotations

import pandas as pd

from filters.foreign import evaluate as evaluate_foreign
from filters.proprietary import evaluate as evaluate_proprietary
from tests.bars import frame


def _with_net(column: str, values: list[float]) -> pd.DataFrame:
    bars = frame([10.0] * len(values))
    bars[column] = values
    return bars


def test_foreign_net_buy_is_a_buy() -> None:
    result = evaluate_foreign(_with_net("foreign_net_vol", [100.0]), {"days": 1, "min_net_vol": 0})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_foreign_net_sell_is_a_sell() -> None:
    result = evaluate_foreign(_with_net("foreign_net_vol", [-50.0, -80.0]), {"days": 2, "min_net_vol": 0})
    assert result.signal_type == "ban"


def test_foreign_waits_without_the_column() -> None:
    result = evaluate_foreign(frame([10.0, 11.0]))
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"


def test_proprietary_needs_the_minimum_size() -> None:
    bars = _with_net("prop_net_vol", [10.0])
    result = evaluate_proprietary(bars, {"days": 1, "min_net_vol": 100})
    assert result.matched is False
