"""Universe mã cho ingestion — board stocks từ vnstock Listing (1 list, 1 price_board)."""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_SYM_RE = re.compile(r"^[A-Z0-9]{3,}$")


def board_stock_symbols() -> list[str]:
    """Mọi mã ``type=stock`` trên HOSE/HNX/UPCOM (không CW/bond/fund/future)."""
    from vnstock import Listing

    frame = Listing().symbols_by_exchange()
    if frame is None or getattr(frame, "empty", True):
        raise ValueError("Listing.symbols_by_exchange empty")
    work = frame.copy()
    work["symbol"] = work["symbol"].astype(str).str.strip().str.upper()
    if "type" in work.columns:
        work = work[work["type"].astype(str).str.lower() == "stock"]
    symbols = sorted({s for s in work["symbol"] if _SYM_RE.match(s)})
    if not symbols:
        raise ValueError("no stock symbols from Listing")
    return symbols


def resolve_symbols(mode: str, static: list[str]) -> list[str]:
    """``board_stocks`` → Listing; lỗi → fallback static. ``static`` → list YAML/env."""
    cleaned = [s.strip().upper() for s in static if str(s).strip()]
    mode = (mode or "static").strip().lower()
    if mode != "board_stocks":
        return cleaned
    try:
        got = board_stock_symbols()
    except Exception as exc:  # noqa: BLE001 — startup không chết vì Listing
        log.warning("board_stocks listing failed, using static fallback: %s", exc)
        return cleaned
    return got
