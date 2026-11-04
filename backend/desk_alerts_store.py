"""Per-user price alert configs + trigger history (Desk SQLite — Phase 1 Telegram Alerts).

Default DB: ``data/desk_alerts.db`` (override: ``DESK_ALERTS_DB_PATH``).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Condition = Literal["GT", "LT"]
VALID_CONDITIONS = frozenset({"GT", "LT"})

DEFAULT_DB = Path(os.getenv("DESK_ALERTS_DB_PATH", "data/desk_alerts.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_alert_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    condition TEXT NOT NULL CHECK (condition IN ('GT', 'LT')),
    target_value REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_alert_configs_user_active
    ON user_alert_configs(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_user_alert_configs_symbol_active
    ON user_alert_configs(symbol, is_active);

CREATE TABLE IF NOT EXISTS alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_config_id INTEGER NOT NULL,
    triggered_at TEXT NOT NULL,
    last_price REAL NOT NULL,
    FOREIGN KEY (alert_config_id) REFERENCES user_alert_configs(id)
);
CREATE INDEX IF NOT EXISTS idx_alert_history_config_triggered
    ON alert_history(alert_config_id, triggered_at DESC);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_symbol(raw: Any) -> str:
    return str(raw or "").strip().upper()


def normalize_condition(raw: Any) -> Condition:
    cond = str(raw or "").strip().upper()
    if cond not in VALID_CONDITIONS:
        raise ValueError("condition must be GT or LT")
    return cond  # type: ignore[return-value]


def condition_met(condition: str, price: float, target_value: float) -> bool:
    """So sánh giá tick với ngưỡng (biên: bằng target → chưa trigger)."""
    cond = str(condition or "").strip().upper()
    if cond == "GT":
        return float(price) > float(target_value)
    if cond == "LT":
        return float(price) < float(target_value)
    return False


def _row_config(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": str(row["user_id"]),
        "symbol": str(row["symbol"]),
        "condition": str(row["condition"]),
        "target_value": float(row["target_value"]),
        "is_active": bool(row["is_active"]),
        "created_at": str(row["created_at"]),
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


def init_desk_alerts_store(db_path: Path | None = None) -> None:
    """Ensure tables exist (idempotent)."""
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def list_alert_configs(
    user_id: str,
    *,
    active_only: bool = True,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    user = str(user_id or "").strip()
    if not user:
        return []
    sql = """
        SELECT id, user_id, symbol, condition, target_value, is_active, created_at
        FROM user_alert_configs
        WHERE user_id = ?
    """
    params: list[Any] = [user]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY created_at DESC, id DESC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_config(r) for r in rows]


def create_alert_config(
    user_id: str,
    *,
    symbol: str,
    condition: str,
    target_value: float,
    db_path: Path | None = None,
) -> dict[str, Any]:
    user = str(user_id or "").strip()
    if not user:
        raise ValueError("user_id required")
    sym = normalize_symbol(symbol)
    if not sym:
        raise ValueError("symbol required")
    if len(sym) > 32:
        raise ValueError("symbol too long")
    cond = normalize_condition(condition)
    try:
        target = float(target_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("target_value must be a number") from exc
    if not (target > 0):
        raise ValueError("target_value must be > 0")
    now = _utcnow()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO user_alert_configs
                (user_id, symbol, condition, target_value, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (user, sym, cond, target, now),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, user_id, symbol, condition, target_value, is_active, created_at
            FROM user_alert_configs WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    assert row is not None
    return _row_config(row)


def deactivate_alert_config(
    user_id: str,
    alert_id: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Soft-delete: ``is_active = 0``. None nếu không thuộc user hoặc không tồn tại."""
    user = str(user_id or "").strip()
    aid = int(alert_id)
    if not user or aid <= 0:
        return None
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE user_alert_configs
            SET is_active = 0
            WHERE id = ? AND user_id = ? AND is_active = 1
            """,
            (aid, user),
        )
        if cur.rowcount <= 0:
            conn.commit()
            return None
        conn.commit()
        row = conn.execute(
            """
            SELECT id, user_id, symbol, condition, target_value, is_active, created_at
            FROM user_alert_configs WHERE id = ? AND user_id = ?
            """,
            (aid, user),
        ).fetchone()
    return _row_config(row) if row else None


def record_alert_history(
    alert_config_id: int,
    last_price: float,
    *,
    triggered_at: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Ghi lần trigger (Phase 3 worker dùng; Phase 1–2 expose cho test)."""
    ts = triggered_at or _utcnow()
    price = float(last_price)
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO alert_history (alert_config_id, triggered_at, last_price)
            VALUES (?, ?, ?)
            """,
            (int(alert_config_id), ts, price),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, alert_config_id, triggered_at, last_price
            FROM alert_history WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
    assert row is not None
    return {
        "id": int(row["id"]),
        "alert_config_id": int(row["alert_config_id"]),
        "triggered_at": str(row["triggered_at"]),
        "last_price": float(row["last_price"]),
    }


def latest_history_for_config(
    alert_config_id: int,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, alert_config_id, triggered_at, last_price
            FROM alert_history
            WHERE alert_config_id = ?
            ORDER BY triggered_at DESC, id DESC
            LIMIT 1
            """,
            (int(alert_config_id),),
        ).fetchone()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "alert_config_id": int(row["alert_config_id"]),
        "triggered_at": str(row["triggered_at"]),
        "last_price": float(row["last_price"]),
    }


def list_active_alerts_for_symbol(
    symbol: str,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    sym = normalize_symbol(symbol)
    if not sym:
        return []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, symbol, condition, target_value, is_active, created_at
            FROM user_alert_configs
            WHERE symbol = ? AND is_active = 1
            ORDER BY id
            """,
            (sym,),
        ).fetchall()
    return [_row_config(r) for r in rows]


def _parse_iso_ts(raw: str | None) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def seconds_since_last_trigger(
    alert_config_id: int,
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> float | None:
    """None nếu chưa từng fire; ngược lại số giây kể từ ``triggered_at`` mới nhất."""
    hist = latest_history_for_config(alert_config_id, db_path=db_path)
    if not hist:
        return None
    ts = _parse_iso_ts(str(hist.get("triggered_at") or ""))
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (current - ts.astimezone(timezone.utc)).total_seconds())


def is_in_cooldown(
    alert_config_id: int,
    cooldown_sec: float,
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> bool:
    """True nếu còn trong cửa sổ cooldown sau lần fire gần nhất."""
    window = max(0.0, float(cooldown_sec))
    if window <= 0:
        return False
    elapsed = seconds_since_last_trigger(alert_config_id, now=now, db_path=db_path)
    if elapsed is None:
        return False
    return elapsed < window
