"""Khối lượng vượt trung bình theo hướng nến."""

from __future__ import annotations

from filters.volume import evaluate
from tests.bars import frame


def test_volume_spike_on_a_green_bar_is_a_buy() -> None:
    closes = [10.0] * 20 + [12.0]
    opens = [10.0] * 20 + [11.0]
    volumes = [100.0] * 20 + [1000.0]
    result = evaluate(frame(closes, volumes, opens), {"length": 20, "spike": 1.5})
    assert result.signal_type == "mua"


def test_volume_spike_on_a_red_bar_is_a_sell() -> None:
    closes = [10.0] * 20 + [8.0]
    opens = [10.0] * 20 + [11.0]
    volumes = [100.0] * 20 + [1000.0]
    result = evaluate(frame(closes, volumes, opens), {"length": 20, "spike": 1.5})
    assert result.signal_type == "ban"


def test_quiet_volume_does_not_match() -> None:
    result = evaluate(frame([10.0] * 21), {"length": 20, "spike": 1.5})
    assert result.matched is False
