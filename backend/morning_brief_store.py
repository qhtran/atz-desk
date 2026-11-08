"""Morning brief SQLite store (``data/signals.db``).

Tables: ``brief_configs``, ``watchlist_portfolio``, ``daily_briefs``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(os.getenv("SIGNALS_DB_PATH", "data/signals.db"))

STATUS_HOLD = "giu"
STATUS_STOP = "cham_cat_lo"
STATUS_RESIST = "cham_khang_cu"
ALLOWED_STATUS = frozenset({STATUS_HOLD, STATUS_STOP, STATUS_RESIST, "dong", "theo_doi"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS brief_configs (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist_portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    buy_price REAL,
    buy_date TEXT,
    stop_loss REAL,
    resistance REAL,
    status TEXT NOT NULL DEFAULT 'giu',
    note TEXT,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_portfolio_symbol
    ON watchlist_portfolio(symbol);
CREATE TABLE IF NOT EXISTS daily_briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_date TEXT NOT NULL,
    title TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    body_json TEXT,
    tech_appendix_json TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_briefs_date ON daily_briefs(brief_date);
"""

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "timezone": "Asia/Ho_Chi_Minh",
    "title_template": "@All Kg các NĐT bản tin sáng ngày {date}",
    "macro_override": "",
    "index_symbols": ["VNINDEX"],
    "sector_theme_ids": ["ngan_hang", "chung_khoan", "thep", "xay_lap", "ban_le"],
    "tech_symbols": [],
    # Mode 2 (Gemini) — mặc định tắt để giữ ổn định Mode 1
    "ai_mode_enabled": False,
    "gemini_api_key": "",
    "ai_temperature": 0.85,
}

_SECRET_KEYS = frozenset({"gemini_api_key"})
_MASK_PLACEHOLDERS = frozenset({"", "••••", "****", "__UNCHANGED__"})


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _norm_symbol(raw: Any) -> str:
    return str(raw or "").strip().upper()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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


def init_brief_store(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def get_config(db_path: Path | None = None) -> dict[str, Any]:
    out = dict(DEFAULT_CONFIG)
    with connect(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM brief_configs").fetchall()
    for row in rows:
        key = str(row["key"])
        raw = str(row["value"] or "")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def put_config(updates: dict[str, Any], *, db_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(updates, dict):
        raise ValueError("ERR-BRIEF-001: config must be an object")
    now = _utcnow()
    with connect(db_path) as conn:
        for key, value in updates.items():
            k = str(key).strip()
            if not k:
                continue
            if k == "gemini_api_key":
                raw = "" if value is None else str(value).strip()
                if raw in _MASK_PLACEHOLDERS or raw.startswith("••••"):
                    continue  # không ghi đè bằng placeholder / để trống
                if raw in {"__CLEAR__", "CLEAR"}:
                    value = ""
            if k == "ai_temperature":
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("ERR-BRIEF-001: ai_temperature must be a number") from exc
                value = min(max(value, 0.1), 1.0)
            if k == "ai_mode_enabled":
                value = bool(value)
            conn.execute(
                """
                INSERT INTO brief_configs (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (k, _json_dumps(value), now),
            )
        conn.commit()
    return get_config(db_path)


def public_config(db_path: Path | None = None) -> dict[str, Any]:
    """Config cho Admin UI — che ``gemini_api_key``, thêm ``gemini_api_key_set``."""
    cfg = get_config(db_path)
    out = dict(cfg)
    secret = str(cfg.get("gemini_api_key") or "").strip()
    out["gemini_api_key_set"] = bool(secret) or bool(str(os.getenv("GEMINI_API_KEY") or "").strip())
    if secret:
        out["gemini_api_key"] = "••••" + secret[-4:] if len(secret) >= 4 else "••••"
    else:
        out["gemini_api_key"] = ""
    for key in _SECRET_KEYS:
        if key != "gemini_api_key" and key in out:
            out[key] = "••••"
    return out


def _row_watch(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "symbol": str(row["symbol"]),
        "buy_price": row["buy_price"],
        "buy_date": row["buy_date"],
        "stop_loss": row["stop_loss"],
        "resistance": row["resistance"],
        "status": str(row["status"] or STATUS_HOLD),
        "note": row["note"],
        "updated_at": str(row["updated_at"]),
    }


def list_watchbook(*, db_path: Path | None = None) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, symbol, buy_price, buy_date, stop_loss, resistance, status, note, updated_at
            FROM watchlist_portfolio
            ORDER BY symbol COLLATE NOCASE, id
            """
        ).fetchall()
    return [_row_watch(r) for r in rows]


def get_watch_item(item_id: int, *, db_path: Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, symbol, buy_price, buy_date, stop_loss, resistance, status, note, updated_at
            FROM watchlist_portfolio WHERE id = ?
            """,
            (int(item_id),),
        ).fetchone()
    return _row_watch(row) if row else None


def upsert_watch_item(
    *,
    symbol: str,
    buy_price: float | None = None,
    buy_date: str | None = None,
    stop_loss: float | None = None,
    resistance: float | None = None,
    status: str | None = None,
    note: str | None = None,
    item_id: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    sym = _norm_symbol(symbol)
    if not sym:
        raise ValueError("ERR-BRIEF-002: symbol required")
    st = str(status or STATUS_HOLD).strip().lower() or STATUS_HOLD
    if st not in ALLOWED_STATUS:
        raise ValueError(f"ERR-BRIEF-003: invalid status {st}")
    now = _utcnow()
    with connect(db_path) as conn:
        if item_id is not None:
            cur = conn.execute(
                """
                UPDATE watchlist_portfolio
                SET symbol = ?, buy_price = ?, buy_date = ?, stop_loss = ?, resistance = ?,
                    status = ?, note = ?, updated_at = ?
                WHERE id = ?
                """,
                (sym, buy_price, buy_date, stop_loss, resistance, st, note, now, int(item_id)),
            )
            if cur.rowcount <= 0:
                raise ValueError("ERR-BRIEF-004: watch item not found")
            wid = int(item_id)
        else:
            existing = conn.execute(
                "SELECT id FROM watchlist_portfolio WHERE symbol = ?",
                (sym,),
            ).fetchone()
            if existing:
                wid = int(existing["id"])
                conn.execute(
                    """
                    UPDATE watchlist_portfolio
                    SET buy_price = ?, buy_date = ?, stop_loss = ?, resistance = ?,
                        status = ?, note = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (buy_price, buy_date, stop_loss, resistance, st, note, now, wid),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO watchlist_portfolio
                        (symbol, buy_price, buy_date, stop_loss, resistance, status, note, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sym, buy_price, buy_date, stop_loss, resistance, st, note, now),
                )
                wid = int(cur.lastrowid)
        conn.commit()
    item = get_watch_item(wid, db_path=db_path)
    assert item is not None
    return item


def delete_watch_item(item_id: int, *, db_path: Path | None = None) -> bool:
    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM watchlist_portfolio WHERE id = ?", (int(item_id),))
        conn.commit()
        return cur.rowcount > 0


def update_watch_status(
    item_id: int,
    status: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    st = str(status or "").strip().lower()
    if st not in ALLOWED_STATUS:
        raise ValueError(f"ERR-BRIEF-003: invalid status {st}")
    now = _utcnow()
    with connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE watchlist_portfolio SET status = ?, updated_at = ? WHERE id = ?",
            (st, now, int(item_id)),
        )
        conn.commit()
        if cur.rowcount <= 0:
            return None
    return get_watch_item(item_id, db_path=db_path)


def replace_watchbook(items: list[dict[str, Any]], *, db_path: Path | None = None) -> list[dict[str, Any]]:
    """Replace entire curated book (admin bulk save)."""
    if not isinstance(items, list):
        raise ValueError("ERR-BRIEF-005: watchbook must be a list")
    with connect(db_path) as conn:
        conn.execute("DELETE FROM watchlist_portfolio")
        conn.commit()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        upsert_watch_item(
            symbol=str(raw.get("symbol") or ""),
            buy_price=_as_float(raw.get("buy_price")),
            buy_date=(str(raw["buy_date"]) if raw.get("buy_date") is not None else None),
            stop_loss=_as_float(raw.get("stop_loss")),
            resistance=_as_float(raw.get("resistance")),
            status=str(raw.get("status") or STATUS_HOLD),
            note=(str(raw["note"]) if raw.get("note") is not None else None),
            db_path=db_path,
        )
    return list_watchbook(db_path=db_path)


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN guard


def save_daily_brief(
    *,
    brief_date: str,
    title: str,
    body_markdown: str,
    body_json: dict[str, Any] | None = None,
    tech_appendix: dict[str, Any] | list[Any] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    day = str(brief_date or "").strip()
    if not day:
        raise ValueError("ERR-BRIEF-006: brief_date required")
    now = _utcnow()
    body_j = _json_dumps(body_json) if body_json is not None else None
    tech_j = _json_dumps(tech_appendix) if tech_appendix is not None else None
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO daily_briefs
                (brief_date, title, body_markdown, body_json, tech_appendix_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(brief_date) DO UPDATE SET
                title = excluded.title,
                body_markdown = excluded.body_markdown,
                body_json = excluded.body_json,
                tech_appendix_json = excluded.tech_appendix_json,
                created_at = excluded.created_at
            """,
            (day, str(title or ""), str(body_markdown or ""), body_j, tech_j, now),
        )
        conn.commit()
    item = get_brief_by_date(day, db_path=db_path)
    assert item is not None
    return item


def get_brief_by_date(brief_date: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, brief_date, title, body_markdown, body_json, tech_appendix_json, created_at
            FROM daily_briefs WHERE brief_date = ?
            """,
            (str(brief_date).strip(),),
        ).fetchone()
    return _row_brief(row) if row else None


def get_latest_brief(*, db_path: Path | None = None) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, brief_date, title, body_markdown, body_json, tech_appendix_json, created_at
            FROM daily_briefs
            ORDER BY brief_date DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return _row_brief(row) if row else None


def _row_brief(row: sqlite3.Row) -> dict[str, Any]:
    body_json = None
    tech = None
    if row["body_json"]:
        try:
            body_json = json.loads(str(row["body_json"]))
        except json.JSONDecodeError:
            body_json = None
    if row["tech_appendix_json"]:
        try:
            tech = json.loads(str(row["tech_appendix_json"]))
        except json.JSONDecodeError:
            tech = None
    return {
        "id": int(row["id"]),
        "brief_date": str(row["brief_date"]),
        "title": str(row["title"]),
        "body_markdown": str(row["body_markdown"]),
        "body_json": body_json,
        "tech_appendix": tech,
        "created_at": str(row["created_at"]),
    }


def seed_watchbook_from_yaml(path: Path, *, db_path: Path | None = None) -> int:
    """Bootstrap curated rows if watchbook empty. Returns inserted count."""
    if list_watchbook(db_path=db_path):
        return 0
    if not path.is_file():
        return 0
    try:
        import yaml
    except ImportError:
        return 0
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, Exception):
        return 0
    items = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return 0
    replace_watchbook(items, db_path=db_path)
    return len(list_watchbook(db_path=db_path))
