"""Đọc ghi sáu bảng tín hiệu. Caller truyền dict, hàm này lo JSON và SQL."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

SIGNAL_TYPES = frozenset({"mua", "ban", "giu", "cho"})
_USER_JSON = ("cai_dat_chung",)
_FILTER_JSON = ("parameters",)
_RULE_JSON = ("definition",)
_SIGNAL_JSON = ("details",)
_CACHE_JSON = ("indicators",)


class DuplicateNotification(Exception):
    """Đã có log gửi thành công cho cùng user, mã, filter và ngày nến."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _row(row: sqlite3.Row | None, json_fields: tuple[str, ...]) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    for field in json_fields:
        item[field] = json.loads(item[field])
    return item


def _rows(rows: list[sqlite3.Row], json_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [item for row in rows if (item := _row(row, json_fields)) is not None]


def ensure_user(conn: sqlite3.Connection, username: str, email: str | None = None) -> int:
    """Tạo user nếu chưa có và trả id.

    Username sau này lấy từ header X-authentik-username. Không có header thì dùng 'local'.
    Hàm này không đọc header, để nguồn định danh đổi mà không sửa repository.
    """
    name = username.strip()
    if not name:
        raise ValueError("thiếu username")
    found = conn.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone()
    if found is not None:
        return int(found["id"])
    cursor = conn.execute(
        """
        INSERT INTO users (username, email_nhan_thong_bao, cai_dat_chung, created_at)
        VALUES (?, ?, '{}', ?)
        """,
        (name, email, _now()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row(row, _USER_JSON)


def get_user_by_username(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    return _row(row, _USER_JSON)


def set_user_settings(
    conn: sqlite3.Connection,
    user_id: int,
    cai_dat_chung: dict[str, Any],
    email: str | None,
) -> None:
    """Ghi đè email và JSON cài đặt. Ném LookupError nếu user không tồn tại."""
    if get_user(conn, user_id) is None:
        raise LookupError("không có user")
    conn.execute(
        "UPDATE users SET email_nhan_thong_bao = ?, cai_dat_chung = ? WHERE id = ?",
        (email, _dump(cai_dat_chung), user_id),
    )
    conn.commit()


def save_filter_config(
    conn: sqlite3.Connection,
    user_id: int,
    filter_name: str,
    parameters: dict[str, Any],
    enabled: bool = True,
    thu_tu: int = 0,
) -> int:
    """Thêm hoặc ghi đè một filter của đúng user. Trả id dòng."""
    if get_user(conn, user_id) is None:
        raise LookupError("không có user")
    name = filter_name.strip()
    if not name:
        raise ValueError("thiếu tên filter")
    conn.execute(
        """
        INSERT INTO user_filter_configs
            (user_id, filter_name, parameters, enabled, thu_tu, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, filter_name) DO UPDATE SET
            parameters = excluded.parameters,
            enabled = excluded.enabled,
            thu_tu = excluded.thu_tu,
            updated_at = excluded.updated_at
        """,
        (user_id, name, _dump(parameters), int(enabled), thu_tu, _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM user_filter_configs WHERE user_id = ? AND filter_name = ?",
        (user_id, name),
    ).fetchone()
    return int(row["id"])


def list_filter_configs(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM user_filter_configs
        WHERE user_id = ?
        ORDER BY thu_tu, id
        """,
        (user_id,),
    ).fetchall()
    return _rows(rows, _FILTER_JSON)


def delete_filter_configs(conn: sqlite3.Connection, user_id: int) -> None:
    """Xóa mọi config filter của một user. Dùng khi import chế độ replace."""
    conn.execute("DELETE FROM user_filter_configs WHERE user_id = ?", (user_id,))
    conn.commit()


def add_composite_rule(
    conn: sqlite3.Connection,
    name: str,
    owner: str,
    definition: dict[str, Any],
    mo_ta: str = "",
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO composite_rules (name, owner, definition, mo_ta, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name.strip(), owner.strip(), _dump(definition), mo_ta, _now()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_composite_rules(conn: sqlite3.Connection, owner: str | None = None) -> list[dict[str, Any]]:
    if owner is None:
        rows = conn.execute("SELECT * FROM composite_rules ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM composite_rules WHERE owner = ? ORDER BY id",
            (owner,),
        ).fetchall()
    return _rows(rows, _RULE_JSON)



def delete_composite_rules(conn: sqlite3.Connection, owner: str) -> None:
    """Xóa composite của một owner. Import replace dùng hàm này."""
    conn.execute("DELETE FROM composite_rules WHERE owner = ?", (owner,))
    conn.commit()


def record_signal(
    conn: sqlite3.Connection,
    user_id: int,
    symbol: str,
    filter_name: str,
    signal_type: str,
    bar_date: str,
    details: dict[str, Any] | None = None,
    gia_tai_thoi_diem: float | None = None,
) -> tuple[int, bool]:
    """Ghi một tín hiệu. Trả (id, created).

    created là False khi đã có dòng cùng user, mã, filter và ngày nến.
    """
    if signal_type not in SIGNAL_TYPES:
        raise ValueError("loại tín hiệu không hỗ trợ")
    if get_user(conn, user_id) is None:
        raise LookupError("không có user")
    code = symbol.strip().upper()
    name = filter_name.strip()
    try:
        cursor = conn.execute(
            """
            INSERT INTO signal_history (
                user_id, symbol, filter_name, signal_type, detected_at,
                details, notified, gia_tai_thoi_diem, bar_date
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (user_id, code, name, signal_type, _now(), _dump(details or {}), gia_tai_thoi_diem, bar_date),
        )
        conn.commit()
        return int(cursor.lastrowid), True
    except sqlite3.IntegrityError:
        conn.rollback()
        row = conn.execute(
            """
            SELECT id FROM signal_history
            WHERE user_id = ? AND symbol = ? AND filter_name = ? AND bar_date = ?
            """,
            (user_id, code, name, bar_date),
        ).fetchone()
        if row is None:
            raise
        return int(row["id"]), False


def list_signals(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM signal_history WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    return _rows(rows, _SIGNAL_JSON)


def mark_signal_notified(conn: sqlite3.Connection, signal_id: int) -> None:
    conn.execute("UPDATE signal_history SET notified = 1 WHERE id = ?", (signal_id,))
    conn.commit()


def save_market_bar(
    conn: sqlite3.Connection,
    symbol: str,
    timeframe: str,
    bar_date: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    indicators: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO market_data_cache (
            symbol, timeframe, bar_date, open, high, low, close, volume, indicators, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, timeframe, bar_date) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume,
            indicators = excluded.indicators,
            updated_at = excluded.updated_at
        """,
        (
            symbol.strip().upper(),
            timeframe,
            bar_date,
            open_,
            high,
            low,
            close,
            volume,
            _dump(indicators),
            _now(),
        ),
    )
    conn.commit()


def get_market_bar(
    conn: sqlite3.Connection,
    symbol: str,
    timeframe: str,
    bar_date: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM market_data_cache
        WHERE symbol = ? AND timeframe = ? AND bar_date = ?
        """,
        (symbol.strip().upper(), timeframe, bar_date),
    ).fetchone()
    return _row(row, _CACHE_JSON)


def notification_sent(
    conn: sqlite3.Connection,
    user_id: int,
    symbol: str,
    filter_name: str,
    bar_date: str,
) -> bool:
    """True nếu đã gửi thành công cho đúng khóa cooldown."""
    row = conn.execute(
        """
        SELECT 1 FROM notification_logs
        WHERE user_id = ? AND symbol = ? AND filter_name = ? AND bar_date = ?
          AND status = 'thành công'
        """,
        (user_id, symbol.strip().upper(), filter_name.strip(), bar_date),
    ).fetchone()
    return row is not None


def log_notification(
    conn: sqlite3.Connection,
    user_id: int,
    signal_history_id: int | None,
    status: str,
    email_to: str | None,
    symbol: str,
    filter_name: str,
    bar_date: str,
    error: str | None = None,
) -> int:
    """Ghi một lần gửi. Lần thành công thứ hai cùng khóa thì ném DuplicateNotification."""
    if status not in {"thành công", "lỗi"}:
        raise ValueError("trạng thái gửi không hỗ trợ")
    try:
        cursor = conn.execute(
            """
            INSERT INTO notification_logs (
                user_id, signal_history_id, sent_at, status, email_to, error,
                symbol, filter_name, bar_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                signal_history_id,
                _now(),
                status,
                email_to,
                error,
                symbol.strip().upper(),
                filter_name.strip(),
                bar_date,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise DuplicateNotification("đã gửi thành công cho ngày nến này") from exc
