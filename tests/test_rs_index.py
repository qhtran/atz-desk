"""RS cổ phiếu so VNINDEX."""

from __future__ import annotations

from filters.rs_index import evaluate
from tests.bars import frame


def _index_and_stock(stock_closes: list[float], index_closes: list[float]):
    stock = frame(stock_closes)
    index = frame(index_closes)
    return stock, index


def test_rs_index_outperforms_is_a_buy() -> None:
    stock, index = _index_and_stock([10.0] * 30 + [12.0], [10.0] * 31)
    result = evaluate(stock, {"index_bars": index, "lookback": 20, "min_edge": 0})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_rs_index_underperforms_does_not_match() -> None:
    stock, index = _index_and_stock([10.0] * 30 + [9.0], [10.0] * 30 + [12.0])
    result = evaluate(stock, {"index_bars": index, "lookback": 20, "min_edge": 0})
    assert result.matched is False


def test_rs_index_waits_without_index() -> None:
    result = evaluate(frame([1.0] * 40), {"lookback": 20})
    assert result.matched is False
    assert "VNINDEX" in result.reason
