"""SQLite: migration an toàn (telegram_chat_id, alert_deliveries), signal_history, delivery log, preference đọc."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from storage.db import connect, migrate

DELIVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_deliveries (
    id INTEGER PRIMARY KEY,
    signal_id TEXT NOT NULL,
    signal_history_id INTEGER,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL,          -- sent | failed | skipped
    error_code TEXT,
    error TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS alert_deliveries_signal ON alert_deliveries (signal_id);
CREATE INDEX IF NOT EXISTS alert_deliveries_user ON alert_deliveries (user_id, created_at);
"""


def migrate_alert(conn: sqlite3.Connection) -> list[str]:
    """Idempotent. Chỉ ADD COLUMN / CREATE IF NOT EXISTS, không xoá dữ liệu."""
    done = []
    migrate(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    if "telegram_chat_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN telegram_chat_id TEXT")
        done.append("users.telegram_chat_id")
    conn.executescript(DELIVERY_SCHEMA)
    conn.commit()
    return done


def open_db(path: str) -> sqlite3.Connection:
    conn = connect(Path(path))
    conn.execute("PRAGMA busy_timeout = 5000")
    migrate_alert(conn)
    return conn


def get_user(conn, user_id: str) -> dict | None:
    if not str(user_id).isdigit():
        return None
    row = conn.execute("SELECT id, username, email_nhan_thong_bao, cai_dat_chung, telegram_chat_id FROM users WHERE id = ?",
                       (int(user_id),)).fetchone()
    if row is None:
        return None
    d = dict(row)
    try:
        d["cai_dat_chung"] = json.loads(d["cai_dat_chung"] or "{}")
    except ValueError:
        d["cai_dat_chung"] = {}
    return d


def record_history(conn, sig: dict) -> int | None:
    """Ghi signal_history (unique user+mã+filter+ngày): trùng ngày -> trả id cũ. User không có trong DB -> None."""
    if get_user(conn, sig["user_id"]) is None:
        return None
    from storage.repository import record_signal
    sig_type = "mua" if sig["direction"] == "BUY" else "ban"
    bar_date = str(sig["timestamp"])[:10]
    details = {k: sig[k] for k in ("signal_id", "reason", "confidence", "timestamp")}
    sid, _ = record_signal(conn, int(sig["user_id"]), sig["symbol"], sig["filter_name"], sig_type, bar_date,
                           details, float(sig["price"]))
    return sid


def log_delivery(conn, sig: dict, hist_id, channel, target, status, error_code=None, error=None, latency_ms=None):
    conn.execute(
        "INSERT INTO alert_deliveries (signal_id, signal_history_id, user_id, channel, target, status, error_code, error, latency_ms, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sig["signal_id"], hist_id, str(sig["user_id"]), channel, None if target is None else str(target), status,
         error_code, error, latency_ms, datetime.now().astimezone().isoformat(timespec="seconds")))
    conn.commit()


def mark_notified(conn, hist_id) -> None:
    if hist_id:
        conn.execute("UPDATE signal_history SET notified = 1 WHERE id = ?", (hist_id,))
        conn.commit()
