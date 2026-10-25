"""Filter plugin advisor."""

from __future__ import annotations

from filters.advisor import FILTER, evaluate
from tests.bars import frame
from tests.test_advisor_score import _uptrend_bars


def test_advisor_filter_matched_has_pillars() -> None:
    bars = _uptrend_bars(volume_spike=4.0)
    result = evaluate(bars, {"buy_min_total": 40.0, "sell_max_total": 20.0})
    assert "pillars" in result.details
    assert result.details["total"] == 100.0
    assert float(result.details["score"]) <= 100.0
    if result.matched:
        assert result.signal_type == "mua"
        assert result.strength == round(float(result.details["score"]) / 100.0, 4)


def test_advisor_filter_waits_on_short_bars() -> None:
    result = evaluate(frame([1.0, 2.0, 3.0]), None)
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"


def test_filter_spec_registered_fields() -> None:
    assert FILTER.name == "advisor"
    assert FILTER.group == "cố vấn"
