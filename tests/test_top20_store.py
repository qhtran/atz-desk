"""Top 20 lưu trong SQLite. DB tạm, không đụng data/signals.db."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

import config
from datasource import cache, top20_store


def _board(n=3, base=10.0):
    return pd.DataFrame({
        "Mã": [f"m{i}" for i in range(n)], "Giá": [base + i for i in range(n)],
        "RS 3 tháng (%)": [5.0] * n, "ROE (%)": [15.0] * n, "KLGD TB 20 phiên": [200000.0] * n,
    })[config.COLUMNS]


@pytest.fixture
def paths(tmp_path, monkeypatch):
    db, csv = tmp_path / "signals.db", tmp_path / "top20_cache.csv"
    monkeypatch.setattr(config, "SIGNALS_DB", db)
    monkeypatch.setattr(config, "CACHE_PATH", csv)
    monkeypatch.setattr(cache, "CACHE_PATH", csv)
    top20_store._MIGRATED.clear()
    yield db, csv
    top20_store._MIGRATED.clear()


def test_empty_returns_columns(paths):
    board, stamp = top20_store.load_latest()
    assert board.empty and list(board.columns) == config.COLUMNS and stamp is None
    assert cache.read_cache().empty


def test_save_then_load_keeps_order_units(paths):
    top20_store.save_snapshot(_board(3, base=60.5))
    board = cache.read_cache()
    assert board["Mã"].tolist() == ["M0", "M1", "M2"]
    assert board["Giá"].tolist() == [60.5, 61.5, 62.5]  # nghìn đồng, không đổi đơn vị
    assert list(board.columns) == config.COLUMNS


def test_latest_snapshot_and_retention(paths):
    for i in range(top20_store.KEEP_SCANS + 3):
        top20_store.save_snapshot(_board(2, base=float(i)))
    assert cache.read_cache()["Giá"].tolist() == [float(i), float(i) + 1]
    conn = sqlite3.connect(paths[0])
    assert conn.execute("SELECT COUNT(DISTINCT scan_id) FROM top20_snapshot").fetchone()[0] == top20_store.KEEP_SCANS
    conn.close()


def test_csv_imported_once_and_not_rewritten(paths):
    db, csv = paths
    _board(4).to_csv(csv, index=False)
    board = cache.read_cache()
    assert len(board) == 4
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT source FROM top20_snapshot LIMIT 1").fetchone()[0] == "csv_import"
    conn.close()
    before = csv.read_bytes()
    top20_store.save_snapshot(_board(2))
    assert csv.read_bytes() == before
    top20_store._MIGRATED.clear()
    assert len(cache.read_cache()) == 2  # không import lại khi bảng đã có dữ liệu


def test_csv_fallback_when_table_empty(paths, monkeypatch):
    _, csv = paths
    _board(2).to_csv(csv, index=False)
    monkeypatch.setattr(top20_store, "_import_csv", lambda conn, p: 0)
    assert len(cache.read_cache()) == 2


def test_missing_columns_rejected(paths):
    with pytest.raises(ValueError):
        top20_store.save_snapshot(pd.DataFrame({"Mã": ["A"]}))


def test_alert_top20_uses_sqlite(paths):
    from datasource import alerts
    top20_store.save_snapshot(_board(2))
    hit, msg = alerts.evaluate(pd.Series({"Mã": "M1", "Loại": "Vào Top 20", "Ngưỡng": None}))
    assert hit and msg == "Đang có trong Top 20 đã lưu."
