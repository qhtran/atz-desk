"""RSI cực trị và chuỗi chưa đủ phiên."""

from __future__ import annotations

from filters.rsi import evaluate
from tests.bars import frame


def test_rsi_buy_after_a_decline() -> None:
    closes = [100 - index for index in range(20)]
    result = evaluate(frame(closes), {"mode": "co_ban", "length": 14, "oversold": 30, "overbought": 70})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_rsi_sell_after_a_rally() -> None:
    closes = [50 + index for index in range(20)]
    result = evaluate(frame(closes), {"mode": "co_ban", "length": 14, "oversold": 30, "overbought": 70})
    assert result.signal_type == "ban"


def test_rsi_waits_without_enough_bars() -> None:
    result = evaluate(frame([1, 2, 3]), {"length": 14})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
