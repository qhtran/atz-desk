"""Trần/sàn / tăng-giảm theo TC."""

from __future__ import annotations

from ui.price_action import limit_prices, price_state
from ui.theme_tokens import CEILING, FLOOR, css_for_price_state


def test_hose_limits_and_states():
    ceil, flr = limit_prices(100_000, "HOSE")
    assert round(ceil) == 107_000 and round(flr) == 93_000
    assert price_state(107_000, 100_000, exchange="HOSE") == "ceiling"
    assert price_state(93_000, 100_000, exchange="HOSE") == "floor"
    assert price_state(101_000, 100_000) == "up"
    assert price_state(99_000, 100_000) == "down"
    assert price_state(100_000, 100_000) == "flat"


def test_css_ceiling_floor():
    assert CEILING in css_for_price_state("ceiling")
    assert FLOOR in css_for_price_state("floor")
