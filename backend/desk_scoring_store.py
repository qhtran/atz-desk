"""Scoring Matrix rules + symbol score history (Desk SQLite).

Default DB: ``data/desk_scoring.db`` (override: ``DESK_SCORING_DB_PATH``).
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(os.getenv("DESK_SCORING_DB_PATH", "data/desk_scoring.db"))

RULE_CODE_MAX = 64
NAME_MAX = 128
CATEGORY_MAX = 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scoring_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_code TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'general',
    name TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    condition_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scoring_rules_active
    ON scoring_rules(is_active, category);

CREATE TABLE IF NOT EXISTS symbol_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    total_score REAL NOT NULL,
    max_score REAL NOT NULL,
    score_pct REAL NOT NULL,
    decision TEXT NOT NULL,
    breakdown_json TEXT NOT NULL,
    indicators_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_symbol_scores_symbol_created
    ON symbol_scores(symbol, created_at DESC);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _parse_json(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return default


def _row_rule(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "rule_code": str(row["rule_code"]),
        "category": str(row["category"] or "general"),
        "name": str(row["name"]),
        "weight": float(row["weight"] or 0),
        "condition_json": _parse_json(row["condition_json"], {}),
        "is_active": bool(row["is_active"]),
        "updated_at": str(row["updated_at"]),
    }


def _row_score(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "symbol": str(row["symbol"]),
        "total_score": float(row["total_score"]),
        "max_score": float(row["max_score"]),
        "score_pct": float(row["score_pct"]),
        "decision": str(row["decision"]),
        "breakdown": _parse_json(row["breakdown_json"], []),
        "indicators": _parse_json(row["indicators_json"], {}),
        "created_at": str(row["created_at"]),
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


def init_desk_scoring_store(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def list_rules(
    *,
    active_only: bool = False,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        if active_only:
            rows = conn.execute(
                """
                SELECT id, rule_code, category, name, weight, condition_json, is_active, updated_at
                FROM scoring_rules
                WHERE is_active = 1
                ORDER BY category COLLATE NOCASE, rule_code COLLATE NOCASE
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, rule_code, category, name, weight, condition_json, is_active, updated_at
                FROM scoring_rules
                ORDER BY category COLLATE NOCASE, rule_code COLLATE NOCASE
                """
            ).fetchall()
    return [_row_rule(r) for r in rows]


def get_rule_by_code(rule_code: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    code = str(rule_code or "").strip().upper()
    if not code:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, rule_code, category, name, weight, condition_json, is_active, updated_at
            FROM scoring_rules WHERE rule_code = ?
            """,
            (code,),
        ).fetchone()
    return _row_rule(row) if row else None


def upsert_rule(
    *,
    rule_code: str,
    name: str,
    weight: float,
    condition_json: Any,
    category: str = "general",
    is_active: bool = True,
    db_path: Path | None = None,
) -> dict[str, Any]:
    code = str(rule_code or "").strip().upper()[:RULE_CODE_MAX]
    title = str(name or "").strip()[:NAME_MAX]
    cat = str(category or "general").strip()[:CATEGORY_MAX] or "general"
    if not code:
        raise ValueError("rule_code required")
    if not title:
        raise ValueError("name required")
    w = float(weight)
    if not isinstance(condition_json, (dict, list)):
        raise ValueError("condition_json must be object or array")
    payload = json.dumps(condition_json, ensure_ascii=False, separators=(",", ":"))
    now = _utcnow()
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO scoring_rules
                (rule_code, category, name, weight, condition_json, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rule_code) DO UPDATE SET
                category = excluded.category,
                name = excluded.name,
                weight = excluded.weight,
                condition_json = excluded.condition_json,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (code, cat, title, w, payload, 1 if is_active else 0, now),
        )
        conn.commit()
    item = get_rule_by_code(code, db_path=db_path)
    assert item is not None
    return item


def save_symbol_score(
    *,
    symbol: str,
    total_score: float,
    max_score: float,
    score_pct: float,
    decision: str,
    breakdown: list[dict[str, Any]],
    indicators: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    sym = str(symbol or "").strip().upper()
    if not sym:
        raise ValueError("symbol required")
    now = _utcnow()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO symbol_scores
                (symbol, total_score, max_score, score_pct, decision,
                 breakdown_json, indicators_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sym,
                float(total_score),
                float(max_score),
                float(score_pct),
                str(decision),
                json.dumps(breakdown, ensure_ascii=False, separators=(",", ":")),
                json.dumps(indicators or {}, ensure_ascii=False, separators=(",", ":")),
                now,
            ),
        )
        conn.commit()
        rid = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT id, symbol, total_score, max_score, score_pct, decision,
                   breakdown_json, indicators_json, created_at
            FROM symbol_scores WHERE id = ?
            """,
            (rid,),
        ).fetchone()
    assert row is not None
    return _row_score(row)


def latest_symbol_score(symbol: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, symbol, total_score, max_score, score_pct, decision,
                   breakdown_json, indicators_json, created_at
            FROM symbol_scores
            WHERE symbol = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (sym,),
        ).fetchone()
    return _row_score(row) if row else None
