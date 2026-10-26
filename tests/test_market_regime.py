"""Regime VNINDEX vs MA."""

from __future__ import annotations

from filters.market_regime import evaluate
from tests.bars import frame


def test_market_regime_bull() -> None:
    closes = [100.0 + i * 0.5 for i in range(60)]
    index = frame(closes)
    result = evaluate(index.iloc[:1], {"index_bars": index, "ma_length": 50})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_market_regime_bear() -> None:
    closes = [200.0 - i * 0.8 for i in range(60)]
    index = frame(closes)
    result = evaluate(index.iloc[:1], {"index_bars": index, "ma_length": 50})
    assert result.matched is True
    assert result.signal_type == "ban"


def test_market_regime_waits_without_index() -> None:
    result = evaluate(frame([1.0] * 60), {"ma_length": 50})
    assert result.matched is False
    assert "VNINDEX" in result.reason
