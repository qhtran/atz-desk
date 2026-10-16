"""Top 20 lưu trong SQLite (bảng top20_snapshot). Mỗi lần quét là một snapshot, giữ KEEP_SCANS bản gần nhất.

Đơn vị giữ nguyên như bảng Top 20 trước đây: "Giá" theo nghìn đồng (đầu ra của scan_top20).
Không còn đọc/ghi CSV.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config

KEEP_SCANS = 10
# cột bảng Top 20 -> cột SQL
_FIELDS = {
    "Mã": "symbol",
    "Giá": "price_k",
    "RS 3 tháng (%)": "rs_3m_pct",
    "ROE (%)": "roe_pct",
    "KLGD TB 20 phiên": "avg_volume_20",
}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS top20_snapshot (
    scan_id       INTEGER NOT NULL,
    scanned_at    TEXT    NOT NULL,
    rank          INTEGER NOT NULL,
    symbol        TEXT    NOT NULL,
    price_k       REAL,
    rs_3m_pct     REAL,
    roe_pct       REAL,
    avg_volume_20 REAL,
    source        TEXT    NOT NULL DEFAULT 'scan',
    PRIMARY KEY (scan_id, rank)
);
CREATE INDEX IF NOT EXISTS idx_top20_snapshot_scan ON top20_snapshot(scan_id);
"""
_LOCK = threading.Lock()
_MIGRATED: set[str] = set()


def _db_path(path: Path | str | None) -> Path:
    return Path(path) if path is not None else Path(config.SIGNALS_DB)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def open_db(path: Path | str | None = None) -> sqlite3.Connection:
    """Mở DB; migration chạy 1 lần/process/đường dẫn. Caller phải close()."""
    db = _db_path(path)
    conn = _connect(db)
    key = str(db.resolve())
    with _LOCK:
        if key not in _MIGRATED:
            conn.executescript(_SCHEMA)
            conn.commit()
            _MIGRATED.add(key)
    return conn


def _num(value):
    value = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(value) else float(value)


def _insert(conn: sqlite3.Connection, board: pd.DataFrame, scanned_at: str, source: str) -> int:
    row = conn.execute("SELECT COALESCE(MAX(scan_id), 0) + 1 FROM top20_snapshot").fetchone()
    scan_id = int(row[0])
    rows = [
        (scan_id, scanned_at, rank, str(item["Mã"]).upper(), _num(item["Giá"]), _num(item["RS 3 tháng (%)"]),
         _num(item["ROE (%)"]), _num(item["KLGD TB 20 phiên"]), source)
        for rank, (_, item) in enumerate(board[config.COLUMNS].iterrows(), start=1)
    ]
    conn.executemany(
        "INSERT INTO top20_snapshot (scan_id, scanned_at, rank, symbol, price_k, rs_3m_pct, roe_pct,"
        " avg_volume_20, source) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.execute("DELETE FROM top20_snapshot WHERE scan_id <= ?", (scan_id - KEEP_SCANS,))
    return scan_id


def save_snapshot(board: pd.DataFrame, path: Path | str | None = None) -> int:
    """Ghi một lần quét. Trả scan_id."""
    missing = [c for c in config.COLUMNS if c not in board.columns]
    if missing:
        raise ValueError(f"thiếu cột {', '.join(missing)}")
    conn = open_db(path)
    try:
        with conn:
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return _insert(conn, board, stamp, "scan")
    finally:
        conn.close()


def load_latest(path: Path | str | None = None) -> tuple[pd.DataFrame, str | None]:
    """Snapshot mới nhất theo thứ tự rank, cột như config.COLUMNS. Bảng trống thì (DataFrame rỗng, None)."""
    conn = open_db(path)
    try:
        latest = conn.execute("SELECT MAX(scan_id) FROM top20_snapshot").fetchone()[0]
        if latest is None:
            return pd.DataFrame(columns=config.COLUMNS), None
        rows = conn.execute(
            "SELECT symbol, price_k, rs_3m_pct, roe_pct, avg_volume_20, scanned_at FROM top20_snapshot"
            " WHERE scan_id = ? ORDER BY rank", (latest,),
        ).fetchall()
    finally:
        conn.close()
    frame = pd.DataFrame([r[:5] for r in rows], columns=list(_FIELDS))
    return frame[config.COLUMNS], (rows[0][5] if rows else None)
