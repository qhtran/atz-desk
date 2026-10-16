"""Position Store (SQLite data/signals.db). Migration additive: chỉ CREATE IF NOT EXISTS.

Giá lưu theo VND (cùng đơn vị quote). Tab Danh mục cũ (data/positions.csv, nghìn đồng) không bị đụng.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from storage.db import connect, migrate

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'LONG',      -- chỉ LONG (thị trường VN không bán khống)
    quantity REAL NOT NULL,
    entry_price REAL NOT NULL,              -- VND
    stop_loss REAL,                         -- VND, NULL = không theo dõi
    take_profit REAL,                       -- VND, NULL = không theo dõi
    status TEXT NOT NULL DEFAULT 'open',    -- open | closed
    note TEXT,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    sl_hit_at TEXT,                         -- đã cảnh báo SL (trigger 1 lần; rearm để bật lại)
    tp_hit_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS positions_open ON positions (status, symbol);
CREATE INDEX IF NOT EXISTS positions_user ON positions (user_id, status);
"""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def migrate_positions(conn: sqlite3.Connection) -> None:
    migrate(conn)
    conn.executescript(SCHEMA)
    conn.commit()


def open_db(path: str) -> sqlite3.Connection:
    conn = connect(Path(path))
    conn.execute("PRAGMA busy_timeout = 5000")
    migrate_positions(conn)
    return conn


def add(conn, user_id: int, symbol: str, quantity: float, entry_price: float,
        stop_loss: float | None = None, take_profit: float | None = None, note: str | None = None,
        opened_at: str | None = None) -> int:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("thiếu mã")
    if quantity <= 0 or entry_price <= 0:
        raise ValueError("quantity và entry_price phải > 0")
    if stop_loss is not None and stop_loss >= entry_price:
        raise ValueError("stop_loss phải < entry_price (vị thế LONG)")
    if take_profit is not None and take_profit <= entry_price:
        raise ValueError("take_profit phải > entry_price (vị thế LONG)")
    if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
        raise ValueError(f"user_id {user_id} không tồn tại")
    now = _now()
    cur = conn.execute(
        "INSERT INTO positions (user_id, symbol, quantity, entry_price, stop_loss, take_profit, note, opened_at, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user_id, symbol, quantity, entry_price, stop_loss, take_profit, note, opened_at or now, now, now))
    conn.commit()
    return int(cur.lastrowid)


def list_open(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM positions WHERE status = 'open' ORDER BY id")]


def list_all(conn, user_id: int | None = None) -> list[dict]:
    if user_id is None:
        return [dict(r) for r in conn.execute("SELECT * FROM positions ORDER BY id")]
    return [dict(r) for r in conn.execute("SELECT * FROM positions WHERE user_id = ? ORDER BY id", (user_id,))]


def close(conn, position_id: int) -> bool:
    now = _now()
    cur = conn.execute("UPDATE positions SET status='closed', closed_at=?, updated_at=? WHERE id=? AND status='open'",
                       (now, now, position_id))
    conn.commit()
    return cur.rowcount == 1


def update_levels(conn, position_id: int, stop_loss=None, take_profit=None) -> None:
    sets, args = [], []
    if stop_loss is not None:
        sets += ["stop_loss = ?", "sl_hit_at = NULL"]; args.append(stop_loss)
    if take_profit is not None:
        sets += ["take_profit = ?", "tp_hit_at = NULL"]; args.append(take_profit)
    if not sets:
        return
    conn.execute(f"UPDATE positions SET {', '.join(sets)}, updated_at = ? WHERE id = ?", (*args, _now(), position_id))
    conn.commit()


def rearm(conn, position_id: int) -> None:
    conn.execute("UPDATE positions SET sl_hit_at = NULL, tp_hit_at = NULL, updated_at = ? WHERE id = ?", (_now(), position_id))
    conn.commit()


def mark_hit(conn, position_id: int, kind: str) -> bool:
    """Atomic: chỉ 1 lần. True nếu lần này là lần đầu (dedup bền qua restart)."""
    col = {"sl": "sl_hit_at", "tp": "tp_hit_at"}[kind]
    cur = conn.execute(f"UPDATE positions SET {col} = ?, updated_at = ? WHERE id = ? AND {col} IS NULL AND status = 'open'",
                       (_now(), _now(), position_id))
    conn.commit()
    return cur.rowcount == 1


def unmark_hit(conn, position_id: int, kind: str) -> None:
    """Publish lỗi -> trả lại trạng thái để lần sau thử lại (không mất cảnh báo)."""
    col = {"sl": "sl_hit_at", "tp": "tp_hit_at"}[kind]
    conn.execute(f"UPDATE positions SET {col} = NULL WHERE id = ?", (position_id,))
    conn.commit()
