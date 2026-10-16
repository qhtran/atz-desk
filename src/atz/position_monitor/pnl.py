"""P&L Calculator + parse quote. Đơn vị: VND."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime


class PnlError(ValueError):
    """ERR-POS-002."""


@dataclass
class Pnl:
    market_value: float
    cost: float
    pnl: float
    pnl_pct: float


def _num(v) -> float | None:
    if v in (None, "", "None", "null"):
        return None
    x = float(v)
    return x if math.isfinite(x) else None


def calc(entry_price, quantity, price) -> Pnl:
    try:
        entry, qty, px = _num(entry_price), _num(quantity), _num(price)
    except (TypeError, ValueError) as e:
        raise PnlError(f"giá trị không phải số: {e}") from e
    if entry is None or entry <= 0:
        raise PnlError(f"entry_price không hợp lệ: {entry_price}")
    if qty is None or qty <= 0:
        raise PnlError(f"quantity không hợp lệ: {quantity}")
    if px is None or px <= 0:
        raise PnlError(f"giá hiện tại không hợp lệ: {price}")
    cost, mv = entry * qty, px * qty
    return Pnl(market_value=round(mv, 2), cost=round(cost, 2), pnl=round(mv - cost, 2),
               pnl_pct=round((px / entry - 1) * 100, 4))


def parse_quote(raw) -> dict | None:
    """quote:{symbol} (JSON) hoặc field stream (chuỗi) -> dict có price float, ts datetime, stale bool."""
    if raw is None:
        return None
    q = json.loads(raw) if isinstance(raw, str) else dict(raw)
    try:
        q["price"] = _num(q.get("price"))
    except (TypeError, ValueError):
        q["price"] = None
    try:
        q["ts"] = datetime.fromisoformat(str(q.get("timestamp")))
    except ValueError:
        q["ts"] = None
    q["stale"] = str(q.get("stale", "")).lower() in ("true", "1")
    return q
