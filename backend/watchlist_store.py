"""Per-user personal watchlists in SQLite (dev.atz.vn iBoard).

Default DB path shares ``data/market.db`` (override: ``WATCHLIST_DB_PATH``).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(
    os.getenv("WATCHLIST_DB_PATH")
    or os.getenv("MARKET_DB_PATH")
    or "data/market.db"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    name TEXT NOT NULL,
    symbols TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_watchlists_user ON user_watchlists(username);
"""

NAME_MAX = 64
SYMBOLS_MAX = 500


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_symbols(raw: Any) -> list[str]:
    """Uppercase unique tickers; drop empties; cap length."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            parsed = [p.strip() for p in raw.replace(";", ",").split(",")]
        raw = parsed
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        sym = str(item or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
        if len(out) >= SYMBOLS_MAX:
            break
    return out


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "name": str(row["name"]),
        "symbols": normalize_symbols(row["symbols"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


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


def init_watchlist_store(db_path: Path | None = None) -> None:
    """Ensure ``user_watchlists`` exists (idempotent)."""
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def list_watchlists(username: str, *, db_path: Path | None = None) -> list[dict[str, Any]]:
    user = str(username or "").strip()
    if not user:
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, username, name, symbols, created_at, updated_at
            FROM user_watchlists
            WHERE username = ?
            ORDER BY name COLLATE NOCASE, id
            """,
            (user,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_watchlist(
    username: str,
    watchlist_id: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    user = str(username or "").strip()
    if not user:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, username, name, symbols, created_at, updated_at
            FROM user_watchlists
            WHERE id = ? AND username = ?
            """,
            (int(watchlist_id), user),
        ).fetchone()
    return _row_to_dict(row) if row else None


def create_watchlist(
    username: str,
    name: str,
    symbols: Any,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    user = str(username or "").strip()
    title = str(name or "").strip()[:NAME_MAX]
    if not user:
        raise ValueError("username required")
    if not title:
        raise ValueError("name required")
    syms = normalize_symbols(symbols)
    now = _utcnow()
    payload = json.dumps(syms, ensure_ascii=False, separators=(",", ":"))
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO user_watchlists (username, name, symbols, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user, title, payload, now, now),
        )
        conn.commit()
        wid = int(cur.lastrowid)
    item = get_watchlist(user, wid, db_path=db_path)
    assert item is not None
    return item


def update_watchlist(
    username: str,
    watchlist_id: int,
    *,
    name: str | None = None,
    symbols: Any | None = None,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    user = str(username or "").strip()
    if not user:
        return None
    existing = get_watchlist(user, watchlist_id, db_path=db_path)
    if existing is None:
        return None
    title = existing["name"]
    if name is not None:
        title = str(name).strip()[:NAME_MAX]
        if not title:
            raise ValueError("name required")
    syms = existing["symbols"]
    if symbols is not None:
        syms = normalize_symbols(symbols)
    now = _utcnow()
    payload = json.dumps(syms, ensure_ascii=False, separators=(",", ":"))
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE user_watchlists
            SET name = ?, symbols = ?, updated_at = ?
            WHERE id = ? AND username = ?
            """,
            (title, payload, now, int(watchlist_id), user),
        )
        conn.commit()
    return get_watchlist(user, watchlist_id, db_path=db_path)


def delete_watchlist(
    username: str,
    watchlist_id: int,
    *,
    db_path: Path | None = None,
) -> bool:
    user = str(username or "").strip()
    if not user:
        return False
    with connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM user_watchlists WHERE id = ? AND username = ?",
            (int(watchlist_id), user),
        )
        conn.commit()
        return cur.rowcount > 0
