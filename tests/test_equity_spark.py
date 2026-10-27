"""Equity intraday spark — session + SQLite 1m + bulk XHT hydrate."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.equity_spark import (
    is_equity_spark_symbol,
    load_equity_spark,
    record_equity_spark_tick,
    _normalize_equity_symbols,
)
from backend.index_spark import trading_date_for
from backend.market_db import (
    init_market_db,
    load_equity_minute_ohlc,
    load_equity_minute_series,
    load_equity_series_map,
)
from backend.ssi_rest_bootstrap import TZ_VN

VN = TZ_VN


def _dt(h: int, m: int, wd: int = 0) -> datetime:
    base = datetime(2026, 10, 26, h, m, tzinfo=VN)
    while base.weekday() != wd:
        base += timedelta(days=1)
    return base


class _FakeRedis:
    def __init__(self, store: dict[str, str] | None = None) -> None:
        self.store = dict(store or {})

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value
        return True


def test_is_equity_spark_symbol():
    assert is_equity_spark_symbol({"symbol": "FPT", "kind": "equity", "last": 10})
    assert not is_equity_spark_symbol({"symbol": "VNINDEX", "kind": "index", "last": 1000})


def test_normalize_equity_symbols_drops_index_and_dedupes():
    assert _normalize_equity_symbols(["fpt", "FPT", "VNINDEX", "VN30F1M", ""]) == ["FPT"]


def test_record_equity_spark_tick_persists(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    tick = {"symbol": "FPT", "kind": "equity", "last": 25.5}
    clock = _dt(10, 15)
    ok = record_equity_spark_tick(tick, clock=clock)
    assert ok is True
    td = trading_date_for(clock)
    series = load_equity_minute_series("FPT", td, path=db)
    assert len(series) == 1
    assert series[0][1] == pytest.approx(25.5)


def test_load_equity_minute_ohlc_shape(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    tick = {"symbol": "FPT", "kind": "equity", "last": 10.0}
    clock = _dt(10, 20)
    record_equity_spark_tick(tick, clock=clock)
    record_equity_spark_tick({**tick, "last": 10.5}, clock=clock)
    td = trading_date_for(clock)
    bars = load_equity_minute_ohlc("FPT", td, path=db)
    assert len(bars) == 1
    assert set(bars[0].keys()) == {"time", "open", "high", "low", "close"}
    assert bars[0]["high"] >= bars[0]["low"]


def test_load_equity_series_map_bulk(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    clock = _dt(10, 30)
    record_equity_spark_tick({"symbol": "FPT", "kind": "equity", "last": 11.0}, clock=clock)
    record_equity_spark_tick({"symbol": "VIC", "kind": "equity", "last": 44.0}, clock=clock)
    td = trading_date_for(clock)
    got = load_equity_series_map(["FPT", "VIC", "AAA"], td, path=db)
    assert got["FPT"][0][1] == pytest.approx(11.0)
    assert got["VIC"][0][1] == pytest.approx(44.0)
    assert got["AAA"] == []


@pytest.mark.asyncio
async def test_load_equity_spark_from_sqlite(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    clock = _dt(10, 45)
    record_equity_spark_tick({"symbol": "FPT", "kind": "equity", "last": 12.3}, clock=clock)
    td = trading_date_for(clock)
    redis = _FakeRedis()
    payload = await load_equity_spark(redis, symbols=["FPT", "VNINDEX"], trading_date=td)
    assert payload["ok"] is True
    assert payload["trading_date"] == td
    assert "VNINDEX" not in payload["series"]
    assert payload["series"]["FPT"][0][1] == pytest.approx(12.3)
    # Redis warmed for next read
    assert any("FPT" in k for k in redis.store)


@pytest.mark.asyncio
async def test_load_equity_spark_prefers_redis_cache(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    clock = _dt(11, 0)
    td = trading_date_for(clock)
    redis = _FakeRedis(
        {f"priceboard:equity_spark:{td}:FPT": json.dumps([[1_700_000_000, 99.5]])}
    )
    payload = await load_equity_spark(redis, symbols=["FPT"], trading_date=td)
    assert payload["series"]["FPT"] == [[1_700_000_000, 99.5]]


def test_equity_spark_api_route_exists():
    from backend.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/iboard/equity-spark" in paths
