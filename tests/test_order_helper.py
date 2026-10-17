"""Module 6 - Order Action Helper. T1 format chuẩn + copy, T2 lịch sử cách ly user (pos_* riêng tư),
T3 validation ERR-UI-005, T4 details hỏng ERR-UI-006 + dedup. SQLite tạm, không đụng data/signals.db."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from order_helper import core

NOW = datetime(2026, 10, 16, 7, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE signal_history (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, symbol TEXT NOT NULL,
        filter_name TEXT NOT NULL, signal_type TEXT NOT NULL, detected_at TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}',
        notified INTEGER NOT NULL DEFAULT 0, gia_tai_thoi_diem REAL, bar_date TEXT NOT NULL)""")
    return c


def add(c, uid, sym, filt, typ, ago_h, price, sid, reason="r", details=None):
    ts = (NOW - timedelta(hours=ago_h)).isoformat(timespec="seconds")
    d = details if details is not None else json.dumps({"signal_id": sid, "reason": reason})
    c.execute("INSERT INTO signal_history (user_id,symbol,filter_name,signal_type,detected_at,details,gia_tai_thoi_diem,bar_date)"
              " VALUES (?,?,?,?,?,?,?,?)", (uid, sym, filt, typ, ts, d, price, ts[:10] + sid))


def test_t1_format_and_copy():
    s = core.format_signal({"id": 1, "symbol": "vhm", "filter_name": "rsi", "signal_type": "mua",
                            "detected_at": "2026-10-16T06:07:54+00:00", "gia_tai_thoi_diem": 59800.0,
                            "details": json.dumps({"signal_id": "sig_1", "reason": "RSI 28.9 dưới 30.0"})})
    assert "MUA VHM @ 59,800 | rsi | RSI 28.9 dưới 30.0 | 16/10/2026 13:07" in s["text"]
    assert s["copy"] == "MÃ: VHM | HÀNH ĐỘNG: MUA | GIÁ: 59.8"
    assert s["copy"] in s["text"]
    assert core.direction("SELL") == "BÁN" and core.direction("BUY") == "MUA"


def test_format_order_copy_with_qty_sl_tp():
    text = core.format_order_copy(
        symbol="pow",
        direction="MUA",
        price=12500,
        qty=2000,
        stop_loss=11800,
        take_profit=14000,
    )
    assert text == "MÃ: POW | HÀNH ĐỘNG: MUA | KL: 2,000 | GIÁ: 12.5 | SL: 11.8 | TP: 14"


def test_format_signal_reads_sl_tp_from_details():
    s = core.format_signal(
        {
            "id": 2,
            "symbol": "FPT",
            "filter_name": "pos_sl",
            "signal_type": "ban",
            "detected_at": "2026-10-16T06:07:54+00:00",
            "gia_tai_thoi_diem": 100000.0,
            "details": json.dumps(
                {"signal_id": "p1", "qty": 500, "sl": 95000, "tp": 110000, "reason": "cắt lỗ"}
            ),
        }
    )
    assert s["copy"] == "MÃ: FPT | HÀNH ĐỘNG: BÁN | KL: 500 | GIÁ: 100 | SL: 95 | TP: 110"


def test_t2_history_isolated(conn, caplog):
    caplog.set_level(logging.INFO, logger="ui_realtime")
    add(conn, 1, "VHM", "rsi", "mua", 1, 59800, "a")
    add(conn, 1, "FPT", "pos_sl", "ban", 2, 100000, "b")
    add(conn, 2, "HPG", "pos_tp", "ban", 1, 30000, "c")
    add(conn, 1, "SSI", "macd", "mua", 24 * 10, 30000, "old")
    mine = core.history(conn, 1, days=7, now=NOW)
    assert [s["symbol"] for s in mine] == ["VHM", "FPT"]
    assert mine[1]["private"] is True
    assert all(s["symbol"] != "HPG" for s in mine)          # pos_* của user khác không lộ
    assert [s["symbol"] for s in core.history(conn, 2, now=NOW)] == ["HPG"]
    assert [s["symbol"] for s in core.history(conn, 1, side="BÁN", now=NOW)] == ["FPT"]
    assert [s["symbol"] for s in core.history(conn, 1, symbol="vhm", now=NOW)] == ["VHM"]
    assert any("-UI-OAH-HISTORY]" in r.getMessage() for r in caplog.records)
    assert "VHM,MUA,59800,rsi" in core.to_csv(mine)


@pytest.mark.parametrize("kw", [{"days": 0}, {"days": 999}, {"limit": 0}, {"symbol": "V;--"}, {"side": "X"}, {"days": "a"}])
def test_t3_validation(conn, caplog, kw):
    with pytest.raises(core.FilterError):
        core.history(conn, 1, now=NOW, **kw)
    assert any("ERR-UI-005" in r.getMessage() for r in caplog.records)


def test_t4_bad_details_and_dedup(conn, caplog):
    add(conn, 1, "VHM", "rsi", "mua", 1, 59800, "x", details="{oops")
    add(conn, 1, "VHM", "rsi", "mua", 1, 59800, "dup")
    add(conn, 1, "VHM", "rsi", "mua", 1, 59800, "dup")
    rows = core.history(conn, 1, now=NOW)
    assert len(rows) == 2 and rows[-1]["reason"] == ""
    assert any("ERR-UI-006" in r.getMessage() for r in caplog.records)
