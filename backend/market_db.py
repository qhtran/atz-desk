"""Local SQLite market archive (EOD research + index intraday 1m)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

def market_db_path() -> Path:
    return Path(os.getenv("MARKET_DB_PATH", "data/market.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS index_intraday_1m (
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    minute_ts INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    PRIMARY KEY (symbol, trading_date, minute_ts)
);

CREATE TABLE IF NOT EXISTS equity_eod (
    trading_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (trading_date, symbol)
);

CREATE TABLE IF NOT EXISTS foreign_eod (
    trading_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    foreign_buy REAL,
    foreign_sell REAL,
    foreign_net REAL,
    PRIMARY KEY (trading_date, symbol)
);

CREATE TABLE IF NOT EXISTS ingest_log (
    trading_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (trading_date, symbol, source)
);

CREATE TABLE IF NOT EXISTS equity_intraday_1m (
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    minute_ts INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    PRIMARY KEY (symbol, trading_date, minute_ts)
);

CREATE INDEX IF NOT EXISTS idx_equity_eod_date ON equity_eod(trading_date);
CREATE INDEX IF NOT EXISTS idx_index_1m_date ON index_intraday_1m(trading_date, symbol);
CREATE INDEX IF NOT EXISTS idx_equity_1m_date ON equity_intraday_1m(trading_date, symbol);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or market_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_market_db(path: Path | None = None) -> None:
    conn = connect(path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_index_minute_bar(
    symbol: str,
    trading_date: str,
    minute_ts: int,
    last: float,
    *,
    path: Path | None = None,
) -> None:
    sym = symbol.strip().upper()
    price = float(last)
    conn = connect(path)
    try:
        row = conn.execute(
            """
            SELECT open, high, low FROM index_intraday_1m
            WHERE symbol = ? AND trading_date = ? AND minute_ts = ?
            """,
            (sym, trading_date, minute_ts),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO index_intraday_1m
                    (symbol, trading_date, minute_ts, open, high, low, close)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sym, trading_date, minute_ts, price, price, price, price),
            )
        else:
            hi = max(float(row["high"]), price)
            lo = min(float(row["low"]), price)
            conn.execute(
                """
                UPDATE index_intraday_1m
                SET high = ?, low = ?, close = ?
                WHERE symbol = ? AND trading_date = ? AND minute_ts = ?
                """,
                (hi, lo, price, sym, trading_date, minute_ts),
            )
        conn.commit()
    finally:
        conn.close()


def load_index_minute_series(
    symbol: str,
    trading_date: str,
    *,
    path: Path | None = None,
) -> list[tuple[int, float]]:
    sym = symbol.strip().upper()
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            SELECT minute_ts, close FROM index_intraday_1m
            WHERE symbol = ? AND trading_date = ?
            ORDER BY minute_ts ASC
            """,
            (sym, trading_date),
        ).fetchall()
        return [(int(r["minute_ts"]), float(r["close"])) for r in rows]
    finally:
        conn.close()


def load_index_series_map(
    symbols: list[str],
    trading_date: str,
    *,
    path: Path | None = None,
) -> dict[str, list[list[float | int]]]:
    out: dict[str, list[list[float | int]]] = {}
    for sym in symbols:
        pts = load_index_minute_series(sym, trading_date, path=path)
        out[sym] = [[ts, val] for ts, val in pts]
    return out


def upsert_equity_minute_bar(
    symbol: str,
    trading_date: str,
    minute_ts: int,
    last: float,
    *,
    path: Path | None = None,
) -> None:
    sym = symbol.strip().upper()
    price = float(last)
    conn = connect(path)
    try:
        row = conn.execute(
            """
            SELECT open, high, low FROM equity_intraday_1m
            WHERE symbol = ? AND trading_date = ? AND minute_ts = ?
            """,
            (sym, trading_date, minute_ts),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO equity_intraday_1m
                    (symbol, trading_date, minute_ts, open, high, low, close)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sym, trading_date, minute_ts, price, price, price, price),
            )
        else:
            hi = max(float(row["high"]), price)
            lo = min(float(row["low"]), price)
            conn.execute(
                """
                UPDATE equity_intraday_1m
                SET high = ?, low = ?, close = ?
                WHERE symbol = ? AND trading_date = ? AND minute_ts = ?
                """,
                (hi, lo, price, sym, trading_date, minute_ts),
            )
        conn.commit()
    finally:
        conn.close()


def load_equity_minute_series(
    symbol: str,
    trading_date: str,
    *,
    path: Path | None = None,
) -> list[tuple[int, float]]:
    sym = symbol.strip().upper()
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            SELECT minute_ts, close FROM equity_intraday_1m
            WHERE symbol = ? AND trading_date = ?
            ORDER BY minute_ts ASC
            """,
            (sym, trading_date),
        ).fetchall()
        return [(int(r["minute_ts"]), float(r["close"])) for r in rows]
    finally:
        conn.close()


def load_equity_minute_ohlc(
    symbol: str,
    trading_date: str,
    *,
    path: Path | None = None,
) -> list[dict[str, float | int]]:
    sym = symbol.strip().upper()
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            SELECT minute_ts, open, high, low, close FROM equity_intraday_1m
            WHERE symbol = ? AND trading_date = ?
            ORDER BY minute_ts ASC
            """,
            (sym, trading_date),
        ).fetchall()
        return [
            {
                "time": int(r["minute_ts"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            }
            for r in rows
        ]
    finally:
        conn.close()
