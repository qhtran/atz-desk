"""Per-user portfolios + trade ledger (Desk SQLite — Milestone 2 Phase 1–2).

Default DB: ``data/desk_portfolio.db`` (override: ``DESK_PORTFOLIO_DB_PATH``).

Separate from Phase D holdings in ``portfolio_store.py`` (qty/avg snapshot).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Side = Literal["BUY", "SELL"]
VALID_SIDES = frozenset({"BUY", "SELL"})

DEFAULT_DB = Path(os.getenv("DESK_PORTFOLIO_DB_PATH", "data/desk_portfolio.db"))

NAME_MAX = 64
DESC_MAX = 512
NOTES_MAX = 512
SYMBOL_MAX = 32

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    cash_balance REAL NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_portfolios_user
    ON portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_user_default
    ON portfolios(user_id, is_default);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL DEFAULT 0,
    trade_date TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_transactions_portfolio_symbol
    ON transactions(portfolio_id, symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_portfolio_date
    ON transactions(portfolio_id, trade_date DESC, id DESC);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_symbol(raw: Any) -> str:
    return str(raw or "").strip().upper()[:SYMBOL_MAX]


def normalize_side(raw: Any) -> Side:
    side = str(raw or "").strip().upper()
    if side not in VALID_SIDES:
        raise ValueError("side must be BUY or SELL")
    return side  # type: ignore[return-value]


def _row_portfolio(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": str(row["user_id"]),
        "name": str(row["name"]),
        "description": str(row["description"] or ""),
        "cash_balance": float(row["cash_balance"] or 0),
        "is_default": bool(row["is_default"]),
        "created_at": str(row["created_at"]),
    }


def _row_tx(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "portfolio_id": int(row["portfolio_id"]),
        "symbol": str(row["symbol"]),
        "side": str(row["side"]),
        "quantity": float(row["quantity"]),
        "price": float(row["price"]),
        "fee": float(row["fee"] or 0),
        "trade_date": str(row["trade_date"]),
        "notes": str(row["notes"] or ""),
    }


@contextmanager
def connect(db_path: Path | None = None):
    path = db_path or DEFAULT_DB
    _ensure_parent(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        yield conn
    finally:
        conn.close()


def init_desk_portfolio_store(db_path: Path | None = None) -> None:
    """Ensure ``portfolios`` / ``transactions`` exist (idempotent)."""
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def list_portfolios(user_id: str, *, db_path: Path | None = None) -> list[dict[str, Any]]:
    user = str(user_id or "").strip()
    if not user:
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, description, cash_balance, is_default, created_at
            FROM portfolios
            WHERE user_id = ?
            ORDER BY is_default DESC, name COLLATE NOCASE, id
            """,
            (user,),
        ).fetchall()
    return [_row_portfolio(r) for r in rows]


def get_portfolio(
    user_id: str,
    portfolio_id: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    user = str(user_id or "").strip()
    if not user:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, user_id, name, description, cash_balance, is_default, created_at
            FROM portfolios
            WHERE id = ? AND user_id = ?
            """,
            (int(portfolio_id), user),
        ).fetchone()
    return _row_portfolio(row) if row else None


def create_portfolio(
    user_id: str,
    name: str,
    *,
    description: str = "",
    cash_balance: float = 0.0,
    is_default: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    user = str(user_id or "").strip()
    title = str(name or "").strip()[:NAME_MAX]
    if not user:
        raise ValueError("user_id required")
    if not title:
        raise ValueError("name required")
    cash = float(cash_balance or 0)
    if cash < 0:
        raise ValueError("cash_balance must be >= 0")
    desc = str(description or "").strip()[:DESC_MAX]
    now = _utcnow()
    with connect(db_path) as conn:
        if is_default:
            conn.execute(
                "UPDATE portfolios SET is_default = 0 WHERE user_id = ?",
                (user,),
            )
        cur = conn.execute(
            """
            INSERT INTO portfolios
                (user_id, name, description, cash_balance, is_default, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user, title, desc, cash, 1 if is_default else 0, now),
        )
        conn.commit()
        pid = int(cur.lastrowid)
    item = get_portfolio(user, pid, db_path=db_path)
    assert item is not None
    return item


def delete_portfolio(
    user_id: str,
    portfolio_id: int,
    *,
    db_path: Path | None = None,
) -> bool:
    user = str(user_id or "").strip()
    if not user:
        return False
    with connect(db_path) as conn:
        # Cascade via FK; also delete txs explicitly for older SQLite builds.
        conn.execute(
            "DELETE FROM transactions WHERE portfolio_id = ?",
            (int(portfolio_id),),
        )
        cur = conn.execute(
            "DELETE FROM portfolios WHERE id = ? AND user_id = ?",
            (int(portfolio_id), user),
        )
        conn.commit()
        return cur.rowcount > 0


def position_qty(
    portfolio_id: int,
    symbol: str,
    *,
    db_path: Path | None = None,
) -> float:
    """Net open quantity for ``symbol`` in portfolio (BUY − SELL)."""
    sym = normalize_symbol(symbol)
    if not sym:
        return 0.0
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(
                CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END
            ), 0) AS qty
            FROM transactions
            WHERE portfolio_id = ? AND symbol = ?
            """,
            (int(portfolio_id), sym),
        ).fetchone()
    return float(row["qty"] if row else 0)


def list_positions(
    portfolio_id: int,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Aggregate net qty / avg buy cost per symbol (qty > 0 only)."""
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                symbol,
                SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS qty,
                SUM(CASE WHEN side = 'BUY' THEN quantity * price ELSE 0 END) AS buy_notional,
                SUM(CASE WHEN side = 'BUY' THEN quantity ELSE 0 END) AS buy_qty
            FROM transactions
            WHERE portfolio_id = ?
            GROUP BY symbol
            HAVING qty > 1e-9
            ORDER BY symbol
            """,
            (int(portfolio_id),),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        qty = float(row["qty"] or 0)
        buy_qty = float(row["buy_qty"] or 0)
        buy_notional = float(row["buy_notional"] or 0)
        avg = (buy_notional / buy_qty) if buy_qty > 0 else 0.0
        out.append(
            {
                "symbol": str(row["symbol"]),
                "qty": qty,
                "avg": round(avg, 6),
            }
        )
    return out


def list_transactions(
    user_id: str,
    portfolio_id: int,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]] | None:
    """Return txs or ``None`` if portfolio missing / not owned."""
    if get_portfolio(user_id, portfolio_id, db_path=db_path) is None:
        return None
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, portfolio_id, symbol, side, quantity, price, fee, trade_date, notes
            FROM transactions
            WHERE portfolio_id = ?
            ORDER BY trade_date DESC, id DESC
            """,
            (int(portfolio_id),),
        ).fetchall()
    return [_row_tx(r) for r in rows]


def add_transaction(
    user_id: str,
    portfolio_id: int,
    *,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    fee: float = 0.0,
    trade_date: str | None = None,
    notes: str = "",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Insert trade and update ``cash_balance``. Raises ``ValueError`` on bad input."""
    folio = get_portfolio(user_id, portfolio_id, db_path=db_path)
    if folio is None:
        raise LookupError("portfolio not found")

    sym = normalize_symbol(symbol)
    if not sym:
        raise ValueError("symbol required")
    side_n = normalize_side(side)
    qty = float(quantity)
    px = float(price)
    fee_n = float(fee or 0)
    if qty <= 0:
        raise ValueError("quantity must be > 0")
    if px <= 0:
        raise ValueError("price must be > 0")
    if fee_n < 0:
        raise ValueError("fee must be >= 0")

    notional = qty * px
    cash = float(folio["cash_balance"])
    if side_n == "BUY":
        cost = notional + fee_n
        if cost > cash + 1e-9:
            raise ValueError("insufficient cash_balance")
        new_cash = cash - cost
    else:
        held = position_qty(portfolio_id, sym, db_path=db_path)
        if qty > held + 1e-9:
            raise ValueError("insufficient quantity")
        new_cash = cash + notional - fee_n

    when = str(trade_date or "").strip() or _utcnow()
    note = str(notes or "").strip()[:NOTES_MAX]

    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions
                (portfolio_id, symbol, side, quantity, price, fee, trade_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (int(portfolio_id), sym, side_n, qty, px, fee_n, when, note),
        )
        conn.execute(
            "UPDATE portfolios SET cash_balance = ? WHERE id = ? AND user_id = ?",
            (new_cash, int(portfolio_id), str(user_id).strip()),
        )
        conn.commit()
        tid = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT id, portfolio_id, symbol, side, quantity, price, fee, trade_date, notes
            FROM transactions WHERE id = ?
            """,
            (tid,),
        ).fetchone()
    assert row is not None
    return _row_tx(row)


def delete_transaction(
    user_id: str,
    portfolio_id: int,
    tx_id: int,
    *,
    db_path: Path | None = None,
) -> bool:
    """Remove one trade and reverse its cash impact. Recomputes cash from ledger."""
    folio = get_portfolio(user_id, portfolio_id, db_path=db_path)
    if folio is None:
        return False
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, portfolio_id, symbol, side, quantity, price, fee, trade_date, notes
            FROM transactions
            WHERE id = ? AND portfolio_id = ?
            """,
            (int(tx_id), int(portfolio_id)),
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM transactions WHERE id = ?", (int(tx_id),))
        # Recompute cash from remaining ledger relative to current cash reverse:
        # Prefer: cash = prior_cash ± reverse of deleted row, then verify qty non-negative.
        tx = _row_tx(row)
        cash = float(folio["cash_balance"])
        notional = float(tx["quantity"]) * float(tx["price"])
        fee_n = float(tx["fee"])
        if tx["side"] == "BUY":
            cash = cash + notional + fee_n
        else:
            cash = cash - notional + fee_n
        # Guard: after delete, no symbol may have negative net qty.
        neg = conn.execute(
            """
            SELECT symbol FROM (
                SELECT symbol,
                       SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS qty
                FROM transactions WHERE portfolio_id = ?
                GROUP BY symbol
            ) WHERE qty < -1e-9
            """,
            (int(portfolio_id),),
        ).fetchone()
        if neg is not None:
            conn.rollback()
            raise ValueError("cannot delete: would leave negative quantity")
        conn.execute(
            "UPDATE portfolios SET cash_balance = ? WHERE id = ? AND user_id = ?",
            (cash, int(portfolio_id), str(user_id).strip()),
        )
        conn.commit()
        return True
