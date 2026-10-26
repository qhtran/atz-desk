"""ATR đột biến so trung bình + hướng nến."""

from __future__ import annotations

from filters.atr import evaluate
from tests.bars import frame


def _volatile_bars() -> list[float]:
    base = [10.0] * 25
    # Biên độ lớn ở phiên cuối → ATR tăng vọt so TB.
    return base + [10.0, 10.5, 11.0, 12.0, 15.0]


def test_atr_spike_green_candle_is_a_buy() -> None:
    closes = _volatile_bars()
    bars = frame(closes)
    bars.loc[bars.index[-1], "open"] = 14.0
    bars.loc[bars.index[-1], "close"] = 15.0
    bars.loc[bars.index[-1], "high"] = 16.0
    bars.loc[bars.index[-1], "low"] = 13.5
    result = evaluate(bars, {"length": 14, "avg_length": 10, "spike": 1.1})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_atr_spike_red_candle_is_a_sell() -> None:
    closes = _volatile_bars()
    bars = frame(closes)
    bars.loc[bars.index[-1], "open"] = 15.0
    bars.loc[bars.index[-1], "close"] = 14.0
    bars.loc[bars.index[-1], "high"] = 15.5
    bars.loc[bars.index[-1], "low"] = 13.0
    result = evaluate(bars, {"length": 14, "avg_length": 10, "spike": 1.1})
    assert result.matched is True
    assert result.signal_type == "ban"


def test_atr_waits_without_enough_bars() -> None:
    result = evaluate(frame([1.0, 2.0, 3.0]), {"length": 14, "avg_length": 10, "spike": 1.2})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
