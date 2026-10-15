"""MCDX: Banker cắt qua mốc 0."""

from __future__ import annotations

from filters.mcdx import evaluate
from tests.bars import frame

PARAMS = {
    "banker_period": 5,
    "banker_base": 50,
    "banker_sens": 1.5,
    "hot_period": 4,
    "hot_base": 30,
    "hot_sens": 0.7,
}


def test_mcdx_buy_when_banker_crosses_above_zero() -> None:
    closes = [40, 39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 32, 35]
    result = evaluate(frame([float(price) for price in closes]), PARAMS)
    assert result.matched is True
    assert result.signal_type == "mua"
    assert result.reason == "Banker cắt lên, sức mạnh tăng"
    assert result.details["banker"] > 0


def test_mcdx_sell_when_banker_crosses_below_zero() -> None:
    closes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 17, 13]
    result = evaluate(frame([float(price) for price in closes]), PARAMS)
    assert result.matched is True
    assert result.signal_type == "ban"
    assert result.details["banker"] == 0


def test_mcdx_holds_while_strength_stays_positive() -> None:
    result = evaluate(frame([float(10 + i) for i in range(12)]), PARAMS)
    assert result.matched is False
    assert result.signal_type == "giu"
    assert result.reason == "MCDX chưa cắt"


def test_mcdx_waits_without_enough_bars() -> None:
    result = evaluate(frame([1.0, 2.0, 3.0, 4.0]), PARAMS)
    assert result.matched is False
    assert result.signal_type == "cho"
    assert result.reason == "không đủ dữ liệu"
