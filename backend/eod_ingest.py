"""EOD data pipeline stub — CSV lịch sử + sync từ ``equity_eod`` / ``data/ohlcv``."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from backend.eod_store import count_eod_bars, init_eod_store, upsert_eod_bars

DEFAULT_OHLCV_DIR = Path(os.getenv("OHLCV_BARS_DIR", "data/ohlcv"))


def _pick(row: dict[str, Any], *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return lower[key.lower()]
    return None


def rows_from_csv(path: Path, *, default_symbol: str | None = None) -> list[dict[str, Any]]:
    """Đọc CSV OHLCV. Cột: symbol?, date/trade_date, open, high, low, close, volume."""
    if not path.is_file():
        raise FileNotFoundError(str(path))
    out: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            sym = _pick(raw, "symbol", "ticker", "code") or default_symbol
            day = _pick(raw, "trade_date", "trading_date", "date", "time")
            if not sym or not day:
                continue
            out.append(
                {
                    "symbol": sym,
                    "trade_date": day,
                    "open": _pick(raw, "open", "o"),
                    "high": _pick(raw, "high", "h"),
                    "low": _pick(raw, "low", "l"),
                    "close": _pick(raw, "close", "c", "adj_close"),
                    "volume": _pick(raw, "volume", "vol", "volume_match"),
                }
            )
    return out


def ingest_csv(
    path: Path | str,
    *,
    default_symbol: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    init_eod_store(db_path)
    rows = rows_from_csv(Path(path), default_symbol=default_symbol)
    n = upsert_eod_bars(rows, db_path=db_path)
    return {"ok": True, "source": "csv", "path": str(path), "upserted": n}


def ingest_ohlcv_bars_dir(
    bars_dir: Path | str | None = None,
    *,
    symbols: list[str] | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Import ``{SYMBOL}.csv`` từ thư mục OHLCV Desk (stub pipeline)."""
    root = Path(bars_dir or DEFAULT_OHLCV_DIR)
    init_eod_store(db_path)
    if not root.is_dir():
        return {"ok": False, "source": "ohlcv_dir", "path": str(root), "upserted": 0, "detail": "dir missing"}
    total = 0
    files = 0
    wanted = {s.strip().upper() for s in (symbols or []) if str(s).strip()} or None
    for path in sorted(root.glob("*.csv")):
        sym = path.stem.strip().upper()
        if wanted is not None and sym not in wanted:
            continue
        try:
            rows = rows_from_csv(path, default_symbol=sym)
        except OSError:
            continue
        total += upsert_eod_bars(rows, db_path=db_path)
        files += 1
    return {"ok": True, "source": "ohlcv_dir", "path": str(root), "files": files, "upserted": total}


def sync_from_equity_eod(*, db_path: Path | None = None) -> dict[str, Any]:
    """Copy từ bảng legacy ``equity_eod`` (cùng SQLite market) → ``eod_prices``."""
    init_eod_store(db_path)
    from backend.market_db import connect as market_connect, init_market_db

    init_market_db(db_path)
    conn = market_connect(db_path)
    try:
        # ensure eod_prices exists on same connection path
        init_eod_store(db_path)
        rows = conn.execute(
            """
            SELECT symbol, trading_date AS trade_date, open, high, low, close, volume
            FROM equity_eod
            ORDER BY trading_date, symbol
            """
        ).fetchall()
        payload = [
            {
                "symbol": r["symbol"],
                "trade_date": r["trade_date"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
            }
            for r in rows
        ]
    finally:
        conn.close()
    n = upsert_eod_bars(payload, db_path=db_path)
    return {
        "ok": True,
        "source": "equity_eod",
        "upserted": n,
        "eod_prices_count": count_eod_bars(db_path=db_path),
    }
