"""Equity intraday spark — session + SQLite 1m."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.equity_spark import is_equity_spark_symbol, record_equity_spark_tick
from backend.index_spark import trading_date_for
from backend.market_db import init_market_db, load_equity_minute_series
from backend.ssi_rest_bootstrap import TZ_VN

VN = TZ_VN


def _dt(h: int, m: int, wd: int = 0) -> datetime:
    base = datetime(2026, 10, 26, h, m, tzinfo=VN)
    while base.weekday() != wd:
        base += timedelta(days=1)
    return base


def test_is_equity_spark_symbol():
    assert is_equity_spark_symbol({"symbol": "FPT", "kind": "equity", "last": 10})
    assert not is_equity_spark_symbol({"symbol": "VNINDEX", "kind": "index", "last": 1000})


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
