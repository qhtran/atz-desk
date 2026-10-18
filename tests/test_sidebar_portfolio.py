"""Sidebar quote path: Redis hit, Redis miss → OHLCV fallback, unknown symbol.

Redis is mocked; no live Redis needed. Stale-quote case skipped: live_quotes has
no staleness flag yet.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
import redis

from datasource.live_quotes import load_live_prices_thousands
from ui import sidebar_portfolio as sp
from ui.sidebar_portfolio import (
    desk_position_rows,
    format_sidebar_alert_lines,
    position_alert,
    truncate_sidebar_alert,
)


class _FakeRedis:
    def __init__(self, mapping: dict[str, str] | None = None, exc: Exception | None = None):
        self.mapping = mapping or {}
        self.exc = exc
        self.calls: list[list[str]] = []

    def mget(self, keys):
        self.calls.append(list(keys))
        if self.exc is not None:
            raise self.exc
        return [self.mapping.get(k) for k in keys]


def _store(*rows: dict) -> pd.DataFrame:
    base = {"Giá mua": None, "Vùng hỗ trợ": None, "Vùng kháng cự": None}
    return pd.DataFrame([{**base, **row} for row in rows])


@pytest.fixture
def ohlcv(monkeypatch):
    """Patch OHLCV lookups with a per-symbol close map."""
    closes: dict[str, float | None] = {}
    monkeypatch.setattr(sp, "_bars", lambda symbol: symbol)
    monkeypatch.setattr(sp, "_last_close", lambda frame: closes.get(frame))
    return closes


# --- load_live_prices_thousands -------------------------------------------


def test_redis_hit_normalises_symbols_and_converts_units():
    client = _FakeRedis({"quote:FPT": json.dumps({"price": 58200}), "quote:LPB": json.dumps({"price": 38000.0})})
    got = load_live_prices_thousands([" fpt ", "LPB", ""], client=client)
    assert got == {"FPT": 58.2, "LPB": 38.0}
    assert client.calls == [["quote:FPT", "quote:LPB"]]


def test_redis_custom_quote_key():
    client = _FakeRedis({"q:v1:VIC": json.dumps({"price": 45000})})
    assert load_live_prices_thousands(["VIC"], client=client, quote_key="q:v1:{symbol}") == {"VIC": 45.0}


def test_unknown_symbol_is_dropped():
    client = _FakeRedis({"quote:FPT": json.dumps({"price": 100000})})
    assert load_live_prices_thousands(["FPT", "ZZZZ"], client=client) == {"FPT": 100.0}


def test_malformed_payloads_are_skipped():
    client = _FakeRedis(
        {
            "quote:AAA": "not-json",
            "quote:BBB": json.dumps({"symbol": "BBB"}),
            "quote:CCC": json.dumps({"price": "abc"}),
            "quote:DDD": json.dumps({"price": 21500}),
        }
    )
    assert load_live_prices_thousands(["AAA", "BBB", "CCC", "DDD"], client=client) == {"DDD": 21.5}


@pytest.mark.parametrize(
    "exc",
    [redis.exceptions.ConnectionError("down"), redis.exceptions.TimeoutError("slow"), OSError("net")],
)
def test_redis_error_returns_empty(exc):
    assert load_live_prices_thousands(["FPT"], client=_FakeRedis(exc=exc)) == {}


def test_empty_symbols_skip_redis():
    client = _FakeRedis()
    assert load_live_prices_thousands(["", "  "], client=client) == {}
    assert client.calls == []


# --- desk_position_rows ----------------------------------------------------


def test_rows_redis_hit_beats_ohlcv(ohlcv):
    ohlcv["FPT"] = 91.0
    rows = desk_position_rows(_store({"Mã": "FPT", "Giá mua": 90.0}), 40_000_000, live_prices={"FPT": 99.0})
    assert rows[0]["Giá hiện tại"] == 99.0
    assert rows[0]["price_source"] == "redis"


def test_rows_redis_miss_falls_back_to_ohlcv_per_symbol(ohlcv):
    ohlcv.update({"FPT": 91.0, "VIC": 44.0})
    store = _store({"Mã": "FPT", "Giá mua": 90.0}, {"Mã": "VIC", "Giá mua": 40.0})
    rows = desk_position_rows(store, 40_000_000, live_prices={"FPT": 99.0})
    by_sym = {row["Mã"]: row for row in rows}
    assert (by_sym["FPT"]["Giá hiện tại"], by_sym["FPT"]["price_source"]) == (99.0, "redis")
    assert (by_sym["VIC"]["Giá hiện tại"], by_sym["VIC"]["price_source"]) == (44.0, "ohlcv")


def test_rows_redis_down_uses_ohlcv(monkeypatch, ohlcv):
    """live_prices=None → MGET; a Redis failure yields {} and OHLCV is used."""
    ohlcv["FPT"] = 91.0
    seen: list[list[str]] = []

    def fake_load(symbols):
        seen.append(list(symbols))
        return load_live_prices_thousands(symbols, client=_FakeRedis(exc=redis.exceptions.ConnectionError("down")))

    monkeypatch.setattr(sp, "load_live_prices_thousands", fake_load)
    rows = desk_position_rows(_store({"Mã": "fpt", "Giá mua": 90.0}), 40_000_000)
    assert seen == [["FPT"]]
    assert rows[0]["Giá hiện tại"] == 91.0
    assert rows[0]["price_source"] == "ohlcv"


def test_rows_unknown_symbol_without_any_price(ohlcv):
    rows = desk_position_rows(_store({"Mã": "ZZZZ", "Giá mua": 10.0}), 40_000_000, live_prices={})
    row = rows[0]
    assert row["Giá hiện tại"] is None
    # T-233: cột Cảnh báo = F3 engine; fixture bars giả → —
    assert row["Cảnh báo"] == "—"
    assert row["pnl"] == 0.0
    assert row["mkt"] == row["cost"] == 10_000_000  # 1/4 NAV fallback


def test_rows_skip_blank_and_nan_symbols(ohlcv):
    ohlcv["FPT"] = 91.0
    store = _store({"Mã": "FPT"}, {"Mã": ""}, {"Mã": float("nan")})
    rows = desk_position_rows(store, 40_000_000, live_prices={})
    assert [row["Mã"] for row in rows] == ["FPT"]


def test_rows_pnl_from_live_price(ohlcv):
    store = _store({"Mã": "FPT", "Giá mua": 100.0, "Thăm dò 1/4 NAV": 10_000_000})
    row = desk_position_rows(store, 40_000_000, live_prices={"FPT": 110.0})[0]
    assert row["mkt"] == pytest.approx(11_000_000)
    assert row["pnl"] == pytest.approx(1_000_000)
    assert row["pnl_pct"] == pytest.approx(10.0)
    # T-233: không còn band ±% giá mua trên cột Cảnh báo
    assert row["Cảnh báo"] == "—"


# --- position_alert --------------------------------------------------------


def test_alert_bands_and_zones():
    assert position_alert(None, None) == "Chưa có giá"
    assert position_alert(100.0, 100.0) == "—"
    assert position_alert(100.0, 92.0) == "−8%"
    assert position_alert(100.0, 101.0, support=100.0) == "Gần hỗ trợ"
    assert position_alert(100.0, 95.0, support=100.0) == "Dưới hỗ trợ · −5%"
    assert position_alert(100.0, 121.0, resistance=120.0) == "Gần kháng cự · +10%"


# --- T-235 sidebar alert wrap helpers --------------------------------------


def test_truncate_sidebar_alert_keeps_short():
    short = "xu hướng ngày: giảm"
    assert truncate_sidebar_alert(short) == short
    assert truncate_sidebar_alert("") == "—"
    assert truncate_sidebar_alert("   ") == "—"


def test_truncate_sidebar_alert_long_preview():
    full = "xu hướng ngày: tăng · vượt kháng cự 11.9 (MA20, band giữa)"
    preview = truncate_sidebar_alert(full, max_len=40)
    assert preview.endswith("…")
    assert len(preview) == 40
    assert full.startswith(preview[:-1].rstrip()) or preview[:-1] in full


def test_format_sidebar_alert_lines_full_text():
    full = "xu hướng ngày: tăng · vượt kháng cự 11.9 (MA20, band giữa)"
    lines = format_sidebar_alert_lines(
        [{"Mã": "TPB", "Cảnh báo": full}, {"Mã": "POW", "Cảnh báo": "xu hướng ngày: giảm"}]
    )
    assert lines[0] == f"**TPB:** {full}"
    assert "11.9" in lines[0]
    assert lines[1] == "**POW:** xu hướng ngày: giảm"
