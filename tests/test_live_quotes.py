"""Redis live quotes → nghìn đồng cho sidebar."""

from __future__ import annotations

import json

from datasource.live_quotes import _price_to_thousands, load_live_prices_thousands
from ui.sidebar_portfolio import desk_position_rows
import pandas as pd


class _FakeRedis:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def mget(self, keys):
        return [self.mapping.get(k) for k in keys]


def test_price_to_thousands_vnd_and_already_thousands():
    assert _price_to_thousands(62500) == 62.5
    assert _price_to_thousands(62.5) == 62.5


def test_load_live_prices_from_fake_redis():
    client = _FakeRedis(
        {
            "quote:FPT": json.dumps({"symbol": "FPT", "price": 100000}),
            "quote:VIC": json.dumps({"symbol": "VIC", "price": 45000}),
        }
    )
    got = load_live_prices_thousands(
        ["FPT", "VIC", "AAA"],
        client=client,
        quote_key="quote:{symbol}",
    )
    assert got == {"FPT": 100.0, "VIC": 45.0}


def test_desk_rows_prefer_live_over_empty_ohlcv(monkeypatch):
    store = pd.DataFrame(
        [
            {
                "Mã": "FPT",
                "Giá mua": 90.0,
                "Vùng hỗ trợ": 85.0,
                "Vùng kháng cự": 110.0,
                "Thăm dò 1/4 NAV": 10_000_000,
            }
        ]
    )
    monkeypatch.setattr("ui.sidebar_portfolio._bars", lambda _s: None)
    monkeypatch.setattr("ui.sidebar_portfolio._last_close", lambda _f: None)
    rows = desk_position_rows(store, capital=40_000_000, live_prices={"FPT": 100.0})
    assert rows[0]["Giá hiện tại"] == 100.0
    assert rows[0]["price_source"] == "redis"
    assert rows[0]["pnl"] > 0


def test_desk_rows_ohlcv_when_live_empty(monkeypatch):
    store = pd.DataFrame(
        [{"Mã": "FPT", "Giá mua": 90.0, "Vùng hỗ trợ": None, "Vùng kháng cự": None}]
    )
    monkeypatch.setattr("ui.sidebar_portfolio._bars", lambda _s: "frame")
    monkeypatch.setattr("ui.sidebar_portfolio._last_close", lambda _f: 91.0)
    rows = desk_position_rows(store, capital=40_000_000, live_prices={})
    assert rows[0]["Giá hiện tại"] == 91.0
    assert rows[0]["price_source"] == "ohlcv"
