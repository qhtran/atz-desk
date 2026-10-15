"""MA cắt lên, cắt xuống, và chưa đủ nến."""

from __future__ import annotations

from filters.ma import evaluate
from tests.bars import frame


def test_ma_cross_up_on_the_last_bar() -> None:
    result = evaluate(frame([1, 1, 1, 1, 1, 3]), {"fast": 2, "slow": 4})
    assert result.matched is True
    assert result.signal_type == "mua"


def test_ma_cross_down_on_the_last_bar() -> None:
    result = evaluate(frame([5, 5, 5, 5, 5, 1]), {"fast": 2, "slow": 4})
    assert result.matched is True
    assert result.signal_type == "ban"


def test_ma_waits_when_bars_are_short() -> None:
    result = evaluate(frame([1, 2, 3]), {"fast": 2, "slow": 4})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
