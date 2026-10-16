"""Mở SQLite và tạo schema. Mọi câu SQL khác nằm ở repository."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email_nhan_thong_bao TEXT,
    cai_dat_chung TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_filter_configs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    filter_name TEXT NOT NULL,
    parameters TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    thu_tu INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, filter_name)
);

CREATE TABLE IF NOT EXISTS composite_rules (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    definition TEXT NOT NULL,
    mo_ta TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_history (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    symbol TEXT NOT NULL,
    filter_name TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    notified INTEGER NOT NULL DEFAULT 0,
    gia_tai_thoi_diem REAL,
    bar_date TEXT NOT NULL,
    UNIQUE (user_id, symbol, filter_name, bar_date)
);

CREATE TABLE IF NOT EXISTS market_data_cache (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    bar_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    indicators TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, bar_date)
);

CREATE TABLE IF NOT EXISTS notification_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    signal_history_id INTEGER REFERENCES signal_history(id),
    sent_at TEXT NOT NULL,
    status TEXT NOT NULL,
    email_to TEXT,
    error TEXT,
    symbol TEXT NOT NULL,
    filter_name TEXT NOT NULL,
    bar_date TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS notification_success_once
ON notification_logs (user_id, symbol, filter_name, bar_date)
WHERE status = 'thành công';
"""


def connect(path: Path) -> sqlite3.Connection:
    """Mở một file SQLite. Bật khóa ngoại cho mọi lệnh trên connection này."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Tạo bảng nếu chưa có. Gọi lại trên DB cũ thì không xóa dữ liệu."""
    conn.executescript(SCHEMA)
    conn.commit()


def open_signals(path: Path | None = None) -> sqlite3.Connection:
    """Mở DB tín hiệu của app và tạo bảng nếu chưa có."""
    from config import SIGNALS_DB

    conn = connect(path or SIGNALS_DB)
    migrate(conn)
    return conn
