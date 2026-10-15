"""Ichimoku: giá ra khỏi mây kèm Tenkan cắt Kijun."""

from __future__ import annotations

from filters.ichimoku import evaluate
from tests.bars import frame

PARAMS = {"tenkan": 2, "kijun": 4, "senkou_b": 5, "displacement": 3}


def test_ichimoku_buy_when_price_clears_the_cloud() -> None:
    result = evaluate(frame([8.0] * 6 + [10.0, 10.0]), PARAMS)
    assert result.matched is True
    assert result.signal_type == "mua"
    assert result.reason == "Giá trên mây và Tenkan cắt lên Kijun"


def test_ichimoku_sell_when_price_falls_through_the_cloud() -> None:
    result = evaluate(frame([8.0, 8.0, 8.0, 8.0, 10.0, 10.0, 8.0, 8.0]), PARAMS)
    assert result.matched is True
    assert result.signal_type == "ban"


def test_ichimoku_holds_when_the_cross_is_still_inside_the_cloud() -> None:
    result = evaluate(frame([8.0, 8.0, 8.0, 8.0, 12.0, 8.0, 12.0, 10.0]), PARAMS)
    assert result.matched is False
    assert result.signal_type == "giu"
    assert result.reason == "Tenkan cắt lên nhưng giá chưa trên mây"


def test_ichimoku_waits_without_enough_bars_for_the_cloud() -> None:
    result = evaluate(frame([8.0] * 4), PARAMS)
    assert result.matched is False
    assert result.signal_type == "cho"
    assert result.reason == "không đủ dữ liệu"
