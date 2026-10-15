"""Nến bọc analysis.candles, không tự tính lại thân và bóng."""

from __future__ import annotations

import pandas as pd

from filters.candle import evaluate


def _two(previous: dict, last: dict) -> pd.DataFrame:
    return pd.DataFrame([previous, last])


def test_bullish_engulfing_is_a_buy() -> None:
    bars = _two(
        {"open": 10, "high": 10.2, "low": 7.8, "close": 8},
        {"open": 7, "high": 11.2, "low": 6.8, "close": 11},
    )
    result = evaluate(bars)
    assert result.matched is True
    assert result.signal_type == "mua"
    assert result.details["pattern"] == "Engulfing tăng"


def test_hammer_is_a_buy() -> None:
    bars = _two(
        {"open": 9, "high": 10.2, "low": 8.8, "close": 10},
        {"open": 10, "high": 11.2, "low": 8, "close": 11},
    )
    result = evaluate(bars)
    assert result.signal_type == "mua"
    assert result.details["pattern"] == "Hammer"


def test_one_bar_waits() -> None:
    bars = pd.DataFrame([{"open": 1, "high": 2, "low": 0.5, "close": 1.5}])
    result = evaluate(bars)
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
