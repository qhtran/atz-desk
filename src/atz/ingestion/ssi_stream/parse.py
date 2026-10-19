"""Parse message SSI Market WS → IdxQuote-ish dict (không phụ thuộc schema cứng 100%)."""
from __future__ import annotations

from typing import Any


def normalize_symbol(raw: str | None, aliases: dict[str, str]) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    s = aliases.get(s, aliases.get(s.upper(), s.upper()))
    return s or None


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_market_message(msg: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any] | None:
    """Trả về {symbol, value, ref?, change?, data_time?, kind} hoặc None nếu bỏ qua."""
    if not isinstance(msg, dict):
        return None

    # Heartbeat / control
    method = str(msg.get("method") or "").upper()
    if method in ("PING", "PONG", "SUBSCRIBE", "UNSUBSCRIBE"):
        return None
    ch = str(msg.get("channel") or "").upper()
    if ch == "HEARTBEAT" or method == "PING":
        return None

    # Envelope: data / payload / body
    body = msg
    for k in ("data", "payload", "body", "content"):
        inner = msg.get(k)
        if isinstance(inner, dict):
            body = inner
            break
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            body = inner[0]
            break

    sym = normalize_symbol(
        body.get("symbol") or body.get("s") or body.get("index") or body.get("indexCode") or body.get("Indexcode"),
        aliases,
    )
    if not sym:
        return None

    # index summary style
    val = _num(
        body.get("indexValue")
        or body.get("IndexValue")
        or body.get("value")
        or body.get("p")
        or body.get("price")
        or body.get("last")
        or body.get("c")
        or body.get("close")
    )
    if val is None:
        return None

    chg = _num(body.get("indexChange") or body.get("Change") or body.get("change") or body.get("priceChange"))
    ref = _num(body.get("ref") or body.get("refPrice") or body.get("referencePrice"))
    if ref is None and chg is not None:
        ref = round(val - chg, 2)
    if ref is None:
        pct = _num(body.get("indexChangePercentage") or body.get("ratioChange") or body.get("pct"))
        if pct is not None and abs(pct) < 50:
            # pct dạng % → suy ref
            ref = round(val / (1 + pct / 100.0), 2) if pct != -100 else val
        else:
            ref = val

    data_time = body.get("tradingDate") or body.get("tradingTime") or body.get("t") or body.get("time") or msg.get("time")
    return {
        "symbol": sym,
        "value": val,
        "ref": float(ref),
        "data_time": str(data_time) if data_time is not None else None,
        "kind": str(msg.get("type") or msg.get("event") or body.get("type") or "market"),
    }
