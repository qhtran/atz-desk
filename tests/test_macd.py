"""MACD cắt histogram ở phiên cuối."""

from __future__ import annotations

from filters.macd import evaluate
from tests.bars import frame


def test_macd_cross_up() -> None:
    result = evaluate(frame([10.0] * 40 + [12.0]), {"mode": "co_ban", "fast": 12, "slow": 26, "signal": 9})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_macd_cross_down() -> None:
    result = evaluate(frame([10.0] * 40 + [8.0]), {"mode": "co_ban", "fast": 12, "slow": 26, "signal": 9})
    assert result.signal_type == "ban"


def test_macd_waits_on_a_short_series() -> None:
    result = evaluate(frame([10.0] * 10))
    assert result.reason == "không đủ dữ liệu"
