"""Tests for index-bar session spark helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.index_spark import (
    in_trading_session,
    is_frozen,
    is_index_spark_symbol,
    record_index_spark_tick,
    should_record,
    trading_session_x,
    trading_date_for,
)
from backend.market_db import init_market_db, load_index_minute_series
from backend.ssi_rest_bootstrap import TZ_VN

VN = TZ_VN


def _dt(h: int, m: int, wd: int = 0) -> datetime:
    """Monday=0 … Sunday=6 in Python weekday."""
    base = datetime(2026, 10, 26, h, m, tzinfo=VN)  # Monday
    while base.weekday() != wd:
        base += timedelta(days=1)
    return base


def test_trading_session_x_morning():
    assert trading_session_x(_dt(9, 0)) == pytest.approx(0.0)
    assert trading_session_x(_dt(11, 30)) == pytest.approx(150 / 270)


def test_trading_session_x_lunch():
    assert trading_session_x(_dt(12, 0)) == pytest.approx(150 / 270)


def test_trading_session_x_afternoon():
    assert trading_session_x(_dt(13, 0)) == pytest.approx(150 / 270)
    assert trading_session_x(_dt(15, 0)) == pytest.approx(1.0)


def test_should_record_weekend():
    sat = _dt(10, 0, wd=5)
    assert not should_record(sat)
    assert is_frozen(sat)


def test_should_record_session():
    assert should_record(_dt(10, 0))
    assert not is_frozen(_dt(10, 0))
    assert not should_record(_dt(16, 0))
    assert is_frozen(_dt(16, 0))


def test_is_index_spark_symbol():
    assert is_index_spark_symbol({"symbol": "VNINDEX", "kind": "index", "last": 1200})
    assert not is_index_spark_symbol({"symbol": "FPT", "kind": "equity", "last": 100})


def test_record_index_spark_tick_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    tick = {"symbol": "VNINDEX", "kind": "index", "last": 1288.5}
    clock = _dt(10, 15)
    assert record_index_spark_tick(tick, clock=clock)
    td = trading_date_for(clock)
    series = load_index_minute_series("VNINDEX", td, path=db)
    assert len(series) == 1
    assert series[0][1] == pytest.approx(1288.5)


def test_record_skipped_off_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market.db"
    monkeypatch.setenv("MARKET_DB_PATH", str(db))
    init_market_db(db)
    tick = {"symbol": "VNINDEX", "kind": "index", "last": 1288.5}
    assert not record_index_spark_tick(tick, clock=_dt(18, 0))
    assert load_index_minute_series("VNINDEX", trading_date_for(_dt(18, 0)), path=db) == []
