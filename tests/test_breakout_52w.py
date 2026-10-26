"""Breakout đỉnh lookback."""

from __future__ import annotations

from filters.breakout_52w import evaluate
from tests.bars import frame


def test_breakout_on_last_bar() -> None:
    closes = [10.0] * 59 + [11.0]
    bars = frame(closes)
    bars["high"] = bars["close"] + 0.2
    result = evaluate(bars, {"lookback": 60})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_breakout_holds_when_already_above() -> None:
    closes = [10.0] * 58 + [11.5, 11.6]
    bars = frame(closes)
    bars["high"] = bars["close"] + 0.2
    result = evaluate(bars, {"lookback": 60})
    assert result.matched is False
    assert result.signal_type == "giu"


def test_breakout_waits_on_short_series() -> None:
    result = evaluate(frame([1.0, 2.0, 3.0]), {"lookback": 60})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
