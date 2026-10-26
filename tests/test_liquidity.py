"""Thanh khoản KL + GT trung bình."""

from __future__ import annotations

from filters.liquidity import evaluate
from tests.bars import frame


def test_liquidity_passes_with_high_volume() -> None:
    bars = frame([10.0] * 25, volumes=[200_000.0] * 25)
    result = evaluate(bars, {"length": 20, "min_vol": 100_000, "min_gt": 1_000_000})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_liquidity_fails_when_thin() -> None:
    bars = frame([10.0] * 25, volumes=[1_000.0] * 25)
    result = evaluate(bars, {"length": 20, "min_vol": 100_000, "min_gt": 1_000_000})
    assert result.matched is False


def test_liquidity_waits_on_short_series() -> None:
    result = evaluate(frame([1.0, 2.0]), {"length": 20, "min_vol": 1, "min_gt": 1})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
