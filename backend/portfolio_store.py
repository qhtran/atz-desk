"""Per-user portfolio holdings in SQLite (Phase D — dev priceboard)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(os.getenv("PORTFOLIO_DB_PATH", "data/portfolio.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    username TEXT NOT NULL,
    symbol TEXT NOT NULL,
    qty REAL NOT NULL DEFAULT 0,
    avg REAL NOT NULL DEFAULT 0,
    support REAL,
    resistance REAL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (username, symbol)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_user ON portfolio_holdings(username);
"""


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


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


def list_positions(username: str, *, db_path: Path | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT symbol, qty, avg, support, resistance
            FROM portfolio_holdings
            WHERE username = ?
            ORDER BY symbol
            """,
            (username,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {
            "symbol": str(row["symbol"]),
            "qty": float(row["qty"] or 0),
            "avg": float(row["avg"] or 0),
        }
        if row["support"] is not None:
            item["support"] = float(row["support"])
        if row["resistance"] is not None:
            item["resistance"] = float(row["resistance"])
        out.append(item)
    return out


def replace_positions(
    username: str,
    items: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Replace toàn bộ danh mục user."""
    now = datetime.now(timezone.utc).isoformat()
    cleaned: list[tuple[str, float, float, float | None, float | None]] = []
    seen: set[str] = set()
    for raw in items:
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        qty = float(raw.get("qty") or 0)
        if qty <= 0:
            continue
        avg = float(raw.get("avg") or 0)
        support = raw.get("support")
        resistance = raw.get("resistance")
        sup = float(support) if support is not None and float(support) > 0 else None
        res = float(resistance) if resistance is not None and float(resistance) > 0 else None
        cleaned.append((sym, qty, avg, sup, res))

    with connect(db_path) as conn:
        conn.execute("DELETE FROM portfolio_holdings WHERE username = ?", (username,))
        for sym, qty, avg, sup, res in cleaned:
            conn.execute(
                """
                INSERT INTO portfolio_holdings
                    (username, symbol, qty, avg, support, resistance, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (username, sym, qty, avg, sup, res, now),
            )
        conn.commit()
    return list_positions(username, db_path=db_path)


def migrate_if_empty(
    username: str,
    items: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Import localStorage một lần khi server chưa có dòng nào."""
    existing = list_positions(username, db_path=db_path)
    if existing:
        return False, existing
    saved = replace_positions(username, items, db_path=db_path)
    return True, saved
