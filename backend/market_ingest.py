"""Background EOD ingest into data/market.db (research archive).

Phase 1: schema + ingest_log helpers. Full vnstock/SSI batch — extend ohlcv_seed.
"""

from __future__ import annotations

import time
from pathlib import Path

from backend.market_db import connect, init_market_db, market_db_path


def log_ingest(
    trading_date: str,
    symbol: str,
    source: str,
    status: str,
    detail: str = "",
    *,
    path: Path | None = None,
) -> None:
    init_market_db(path)
    conn = connect(path)
    try:
        conn.execute(
            """
            INSERT INTO ingest_log (trading_date, symbol, source, status, detail, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(trading_date, symbol, source) DO UPDATE SET
                status = excluded.status,
                detail = excluded.detail,
                updated_at = excluded.updated_at
            """,
            (trading_date, symbol.upper(), source, status, detail[:500], int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_market_db_ready() -> Path:
    init_market_db()
    return market_db_path()
