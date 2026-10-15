"""Giá phá dải Bollinger."""

from __future__ import annotations

from filters.bollinger import evaluate
from tests.bars import frame


def test_bollinger_lower_band_is_a_buy() -> None:
    result = evaluate(frame([10.0] * 30 + [1.0]), {"length": 20, "k": 2})
    assert result.signal_type == "mua"
    assert result.matched is True


def test_bollinger_upper_band_is_a_sell() -> None:
    result = evaluate(frame([10.0] * 30 + [20.0]), {"length": 20, "k": 2})
    assert result.signal_type == "ban"


def test_bollinger_inside_band_does_not_match() -> None:
    result = evaluate(frame([10.0] * 30), {"length": 20, "k": 2})
    assert result.matched is False
