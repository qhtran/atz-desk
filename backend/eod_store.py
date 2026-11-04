"""SQLite ``eod_prices`` — OHLCV lịch sử cho EOD analytics (Milestone 3 Phase 1).

Default DB: ``MARKET_DB_PATH`` / ``data/market.db`` (override: ``EOD_DB_PATH``).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB = Path(
    os.getenv("EOD_DB_PATH")
    or os.getenv("MARKET_DB_PATH")
    or "data/market.db"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS eod_prices (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (symbol, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_eod_prices_symbol_date
    ON eod_prices(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_eod_prices_date
    ON eod_prices(trade_date);
"""


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_symbol(raw: Any) -> str:
    return str(raw or "").strip().upper()


def normalize_trade_date(raw: Any) -> str:
    """Chuẩn hoá ngày về ``YYYY-MM-DD`` (chấp nhận ``YYYYMMDD``)."""
    text = str(raw or "").strip()
    if not text:
        raise ValueError("trade_date required")
    digits = text.replace("-", "").replace("/", "")[:8]
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    raise ValueError(f"invalid trade_date: {raw!r}")


@contextmanager
def connect(db_path: Path | None = None):
    path = db_path or DEFAULT_DB
    _ensure_parent(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        yield conn
    finally:
        conn.close()


def init_eod_store(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "symbol": str(row["symbol"]),
        "trade_date": str(row["trade_date"]),
        "open": None if row["open"] is None else float(row["open"]),
        "high": None if row["high"] is None else float(row["high"]),
        "low": None if row["low"] is None else float(row["low"]),
        "close": None if row["close"] is None else float(row["close"]),
        "volume": None if row["volume"] is None else float(row["volume"]),
    }


def upsert_eod_bar(
    *,
    symbol: str,
    trade_date: str,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    close: float | None = None,
    volume: float | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    sym = normalize_symbol(symbol)
    day = normalize_trade_date(trade_date)
    if not sym:
        raise ValueError("symbol required")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO eod_prices (symbol, trade_date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume
            """,
            (sym, day, open_, high, low, close, volume),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT symbol, trade_date, open, high, low, close, volume
            FROM eod_prices WHERE symbol = ? AND trade_date = ?
            """,
            (sym, day),
        ).fetchone()
    assert row is not None
    return _row_to_dict(row)


def upsert_eod_bars(
    rows: Iterable[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> int:
    """Bulk upsert; trả số dòng đã ghi."""
    count = 0
    with connect(db_path) as conn:
        for raw in rows:
            sym = normalize_symbol(raw.get("symbol"))
            if not sym:
                continue
            try:
                day = normalize_trade_date(raw.get("trade_date") or raw.get("date") or raw.get("trading_date"))
            except ValueError:
                continue
            open_ = raw.get("open")
            high = raw.get("high")
            low = raw.get("low")
            close = raw.get("close")
            volume = raw.get("volume")
            conn.execute(
                """
                INSERT INTO eod_prices (symbol, trade_date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
                """,
                (
                    sym,
                    day,
                    None if open_ is None or open_ == "" else float(open_),
                    None if high is None or high == "" else float(high),
                    None if low is None or low == "" else float(low),
                    None if close is None or close == "" else float(close),
                    None if volume is None or volume == "" else float(volume),
                ),
            )
            count += 1
        conn.commit()
    return count


def load_eod_frame(
    symbol: str,
    *,
    start: str | None = None,
    end: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Bars theo ``trade_date`` ASC — input cho indicators."""
    sym = normalize_symbol(symbol)
    if not sym:
        return []
    sql = """
        SELECT symbol, trade_date, open, high, low, close, volume
        FROM eod_prices
        WHERE symbol = ?
    """
    params: list[Any] = [sym]
    if start:
        sql += " AND trade_date >= ?"
        params.append(normalize_trade_date(start))
    if end:
        sql += " AND trade_date <= ?"
        params.append(normalize_trade_date(end))
    sql += " ORDER BY trade_date ASC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_eod_bars(*, symbol: str | None = None, db_path: Path | None = None) -> int:
    with connect(db_path) as conn:
        if symbol:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM eod_prices WHERE symbol = ?",
                (normalize_symbol(symbol),),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM eod_prices").fetchone()
    return int(row["n"] if row else 0)
