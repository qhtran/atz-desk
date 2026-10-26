"""Khối ngoại streak N phiên."""

from __future__ import annotations

import pandas as pd

from filters.foreign_streak import evaluate
from tests.bars import frame


def _with_foreign(values: list[float]) -> pd.DataFrame:
    bars = frame([10.0] * len(values))
    bars["foreign_net_vol"] = values
    return bars


def test_foreign_streak_buy() -> None:
    result = evaluate(_with_foreign([100.0, 120.0, 80.0]), {"days": 3, "min_net_vol": 0})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_foreign_streak_sell() -> None:
    result = evaluate(_with_foreign([-10.0, -20.0, -5.0]), {"days": 3, "min_net_vol": 0})
    assert result.signal_type == "ban"


def test_foreign_streak_waits_without_column() -> None:
    result = evaluate(frame([1.0, 2.0, 3.0]), {"days": 3})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
