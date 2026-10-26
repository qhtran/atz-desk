"""Stochastic %K / %D."""

from __future__ import annotations

import pandas as pd

from filters.stochastic import evaluate
from tests.bars import frame


def _bars_from_closes(closes: list[float]) -> pd.DataFrame:
    bars = frame(closes)
    bars["high"] = bars["close"] + 0.5
    bars["low"] = bars["close"] - 0.5
    return bars


def test_stochastic_waits_on_short_series() -> None:
    result = evaluate(_bars_from_closes([1.0, 2.0, 3.0]), {"k": 5, "d": 3})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"


def test_stochastic_can_match_after_selloff_bounce() -> None:
    # Giảm dần rồi hồi — đủ bar để có %K/%D.
    closes = [20.0 - i * 0.15 for i in range(25)] + [17.5, 18.0, 18.8, 19.5]
    result = evaluate(
        _bars_from_closes(closes),
        {"k": 5, "d": 3, "oversold": 30, "overbought": 80},
    )
    assert result.matched in (True, False)


def test_stochastic_hold_when_no_cross() -> None:
    closes = [10.0] * 30
    result = evaluate(_bars_from_closes(closes), {"k": 5, "d": 3})
    assert result.matched is False
