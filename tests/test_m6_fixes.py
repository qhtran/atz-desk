"""Hồi quy 3 lỗi Module 6 (t137): lọc chiều trong SQL trước LIMIT, giá engine lưu VND, đóng kết nối + migrate 1 lần."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pandas as pd

from order_helper import core

NOW = datetime(2026, 10, 16, 7, 0, tzinfo=timezone.utc)


def _hist():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE signal_history (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, symbol TEXT NOT NULL,
        filter_name TEXT NOT NULL, signal_type TEXT NOT NULL, detected_at TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}',
        notified INTEGER NOT NULL DEFAULT 0, gia_tai_thoi_diem REAL, bar_date TEXT NOT NULL)""")
    return c


def test_side_filter_before_limit():
    c = _hist()
    rows = [("mua", 1), ("buy", 2), ("MUA", 3), ("ban", 4), ("SELL", 5), ("bán", 6)]
    for i, (typ, ago) in enumerate(rows):
        ts = (NOW - timedelta(hours=ago)).isoformat(timespec="seconds")
        c.execute("INSERT INTO signal_history (user_id,symbol,filter_name,signal_type,detected_at,details,gia_tai_thoi_diem,bar_date)"
                  " VALUES (1,'VHM','rsi',?,?,?,1000,?)", (typ, ts, json.dumps({"signal_id": f"s{i}"}), f"d{i}"))
    sells = core.history(c, 1, days=7, limit=1, side="BÁN", now=NOW)
    assert len(sells) == 1 and sells[0]["direction"] == "BÁN"
    assert len(core.history(c, 1, days=7, limit=10, side="BÁN", now=NOW)) == 3
    assert len(core.history(c, 1, days=7, limit=10, side="MUA", now=NOW)) == 3
    assert len(core.history(c, 1, days=7, limit=1, side="MUA", now=NOW)) == 1


def test_engine_stores_price_in_vnd(db):
    from engine import runner
    from filters.base import SignalResult
    from storage.repository import ensure_user

    conn = db
    uid = ensure_user(conn, "u1")
    bars = pd.DataFrame({"time": pd.date_range("2026-09-01", periods=30, freq="D"), "open": 12.0, "high": 12.5,
                         "low": 11.8, "close": 12.2, "volume": 1000.0})

    class Mod:
        @staticmethod
        def evaluate(b, p):
            return SignalResult(matched=True, signal_type="ban", strength=None, reason="x", details={})

    orig = runner.load_registry
    runner.load_registry = lambda: {"proprietary": Mod}
    try:
        reports = runner.run_frames(conn, uid, {"POW": bars}, None,
                                    [{"filter_name": "proprietary", "enabled": 1, "parameters": {}}])
    finally:
        runner.load_registry = orig
    assert reports[0]["price"] == 12200.0
    price = conn.execute("SELECT gia_tai_thoi_diem FROM signal_history").fetchone()[0]
    assert price == 12200.0


def test_open_db_closes_and_migrates_once(tmp_path, monkeypatch):
    from ui_realtime import data
    import alert_dispatcher.store as astore

    calls = []
    real = astore.migrate_alert
    monkeypatch.setattr(astore, "migrate_alert", lambda c: (calls.append(1), real(c)))
    cfg = {"sqlite": {"path": str(tmp_path / "s.db")}}
    from storage.db import connect, migrate
    c0 = connect(tmp_path / "s.db")
    migrate(c0)
    c0.close()
    for _ in range(3):
        with closing(data.open_db(cfg)) as conn:
            conn.execute("SELECT 1 FROM positions LIMIT 1").fetchall()
    assert len(calls) == 1
    try:
        conn.execute("SELECT 1")
        raise AssertionError("connection still open")
    except sqlite3.ProgrammingError:
        pass
