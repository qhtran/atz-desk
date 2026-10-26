"""ADX: +DI cắt -DI khi xu hướng đủ mạnh."""

from __future__ import annotations

import pandas as pd

from analysis.technical import adx as adx_series
from filters.adx import evaluate
from tests.bars import frame


def _bars_with_hlc(closes: list[float]) -> pd.DataFrame:
    bars = frame(closes)
    bars["high"] = bars["close"] + 1.0
    bars["low"] = bars["close"] - 1.0
    return bars


def test_adx_uptrend_is_a_buy() -> None:
    closes = [10.0 + i * 0.3 for i in range(40)]
    result = evaluate(_bars_with_hlc(closes), {"length": 14, "min_adx": 20})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_adx_downtrend_is_a_sell() -> None:
    closes = [40.0 - i * 0.35 for i in range(40)]
    result = evaluate(_bars_with_hlc(closes), {"length": 14, "min_adx": 20})
    assert result.matched is True
    assert result.signal_type == "ban"


def test_adx_waits_on_short_series() -> None:
    result = evaluate(frame([1.0, 2.0, 3.0]), {"length": 14, "min_adx": 25})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"


def test_adx_series_has_values_on_trend() -> None:
    bars = _bars_with_hlc([10.0 + i * 0.2 for i in range(35)])
    line, plus_di, minus_di = adx_series(bars["high"], bars["low"], bars["close"], 14)
    assert not pd.isna(line.iloc[-1])
    assert float(plus_di.iloc[-1]) > float(minus_di.iloc[-1])
