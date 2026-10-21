"""Priceboard tick JSON contract shared by mock + SSI live workers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TZ_VN = timezone(timedelta(hours=7))

INDEX_SYMBOLS = frozenset({"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"})


def now_iso() -> str:
    return datetime.now(TZ_VN).isoformat()


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first_num(body: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        n = _num(body.get(k))
        if n is not None:
            return n
    return None


def _positive_num(v: Any) -> float | None:
    """Numeric field that must be > 0 (ceil/floor/high/low price levels)."""
    n = _num(v)
    if n is None or n <= 0:
        return None
    return n


def _ceil_floor(ref: float, kind: str) -> tuple[float | int, float | int]:
    if kind == "index":
        return round(ref * 1.07, 2), round(ref * 0.93, 2)
    r = int(round(ref))
    return int(round(r * 1.07 / 50) * 50), int(round(r * 0.93 / 50) * 50)


def _book_levels(raw: Any, n: int = 3) -> tuple[list[float], list[float]]:
    """SSI DATA book: [[price, vol], ...] → first n positive prices + vols."""
    prices: list[float] = []
    vols: list[float] = []
    if not isinstance(raw, (list, tuple)):
        return prices, vols
    for row in raw:
        if len(prices) >= n:
            break
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        px = _num(row[0])
        vol = _num(row[1])
        if px is None or px <= 0:
            continue
        prices.append(px)
        vols.append(0.0 if vol is None else vol)
    return prices, vols


def build_tick(
    *,
    symbol: str,
    last: float | int,
    ref: float | int | None = None,
    volume: float | int | None = 0,
    kind: str = "equity",
    exchange: str = "HOSE",
    high: float | int | None = None,
    low: float | int | None = None,
    ceil: float | int | None = None,
    floor: float | int | None = None,
    change: float | int | None = None,
    change_pct: float | None = None,
    bid1: float | int | None = None,
    bid2: float | int | None = None,
    bid3: float | int | None = None,
    bidVol1: float | int | None = None,
    bidVol2: float | int | None = None,
    bidVol3: float | int | None = None,
    ask1: float | int | None = None,
    ask2: float | int | None = None,
    ask3: float | int | None = None,
    askVol1: float | int | None = None,
    askVol2: float | int | None = None,
    askVol3: float | int | None = None,
    matchVol: float | int | None = None,
    foreignBuy: float | int | None = None,
    foreignSell: float | int | None = None,
    source: str = "MOCK_SSI",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize to Frontend contract (symbol, last, ref, ceil, floor, volume, bid*, ask*, …)."""
    sym = str(symbol).strip().upper()
    last_f = float(last)
    ref_f = float(ref) if ref is not None else last_f
    # SSI sometimes sends 0 for missing limits — treat as absent
    if ceil is not None and float(ceil) <= 0:
        ceil = None
    if floor is not None and float(floor) <= 0:
        floor = None
    if ceil is None or floor is None:
        c, f = _ceil_floor(ref_f, kind)
        ceil = ceil if ceil is not None else c
        floor = floor if floor is not None else f

    if change is None:
        change = last_f - ref_f
    if change_pct is None:
        change_pct = (float(change) / ref_f * 100.0) if ref_f else 0.0

    if kind != "index":
        last_out: float | int = int(round(last_f))
        ref_out: float | int = int(round(ref_f))
        change_out: float | int = int(round(float(change)))
        high_out = int(round(float(high if high is not None else last_f)))
        low_out = int(round(float(low if low is not None else last_f)))
        ceil_out = int(ceil)
        floor_out = int(floor)
    else:
        last_out = round(last_f, 2)
        ref_out = round(ref_f, 2)
        change_out = round(float(change), 2)
        high_out = round(float(high if high is not None else last_f), 2)
        low_out = round(float(low if low is not None else last_f), 2)
        ceil_out = float(ceil)
        floor_out = float(floor)

    tick: dict[str, Any] = {
        "type": "tick",
        "symbol": sym,
        "exchange": exchange,
        "kind": kind,
        "last": last_out,
        "ref": ref_out,
        "change": change_out,
        "change_pct": round(float(change_pct), 2),
        "volume": int(volume or 0),
        "high": high_out,
        "low": low_out,
        "ceil": ceil_out,
        "floor": floor_out,
        "ts": now_iso(),
        "source": source,
    }
    # Optional depth / foreign — only include when present (FE enrichDepth fills gaps)
    optional = {
        "bid1": bid1,
        "bid2": bid2,
        "bid3": bid3,
        "bidVol1": bidVol1,
        "bidVol2": bidVol2,
        "bidVol3": bidVol3,
        "ask1": ask1,
        "ask2": ask2,
        "ask3": ask3,
        "askVol1": askVol1,
        "askVol2": askVol2,
        "askVol3": askVol3,
        "matchVol": matchVol,
        "foreignBuy": foreignBuy,
        "foreignSell": foreignSell,
    }
    for k, v in optional.items():
        if v is not None:
            tick[k] = int(round(float(v))) if kind != "index" else v
    if extra:
        tick.update(extra)
    return tick


def parse_ssi_envelope(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Best-effort map SSI WS payload → kwargs for build_tick. None = ignore.

    SSI FastConnect DATA short fields (observed live):
    - Index summary: v=value, c=change, cr=change%, tq=total qty; ce/fl = advance/decline counts (NOT price limits)
    - Equity trade: p=last, v=accumulated volume, o=open/ref, h/l, q=matchVol
    - Equity book: bids/asks = [[price, vol], ...]
    """
    if not isinstance(msg, dict):
        return None
    method = str(msg.get("method") or "").upper()
    channel = str(msg.get("channel") or "").upper()
    if method in ("PING", "PONG", "SUBSCRIBE", "UNSUBSCRIBE"):
        return None
    if channel == "HEARTBEAT":
        return None

    body: Any = msg
    for k in ("data", "payload", "body", "content"):
        inner = msg.get(k)
        if isinstance(inner, dict):
            body = inner
            break
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            body = inner[0]
            break
    if not isinstance(body, dict):
        return None

    sym = (
        body.get("symbol")
        or body.get("s")
        or body.get("StockSymbol")
        or body.get("index")
        or body.get("indexCode")
        or body.get("Indexcode")
    )
    if not sym:
        return None
    sym = str(sym).strip().upper()
    aliases = {
        "HNX-INDEX": "HNXINDEX",
        "HNXINDEX": "HNXINDEX",
        "HNXUPCOMINDEX": "UPCOMINDEX",
        "UPCOM-INDEX": "UPCOMINDEX",
    }
    sym = aliases.get(sym, sym)

    kind = "index" if sym in INDEX_SYMBOLS else "equity"

    # Message shape: indexsummary (v=level) vs trade tick (p=last, v=volume)
    is_index_summary = any(k in body for k in ("adv", "dec", "cr", "tmv", "tvp", "indexValue", "IndexValue")) or (
        kind == "index" and "v" in body and "c" in body and ("tq" in body or "tv" in body)
    )
    is_trade_tick = "p" in body and any(k in body for k in ("q", "si", "o", "a"))

    change = _first_num(body, "indexChange", "Change", "change", "priceChange", "c")
    change_pct = _first_num(
        body,
        "change_pct",
        "changePercent",
        "indexChangePercentage",
        "ratioChange",
        "cr",
    )

    # --- last (kind + shape aware) ---
    # Never use bare `c` as last (change). Never use trade `v` as index last (volume).
    if kind == "index":
        last = _first_num(body, "indexValue", "IndexValue")
        if last is None and is_index_summary:
            last = _first_num(body, "v", "value")
        if last is None and is_trade_tick:
            last = _first_num(body, "p", "last", "LastPrice", "price")
        if last is None:
            # Ambiguous short tick: only accept v when it looks like an index level
            cand = _first_num(body, "value", "last", "LastPrice", "price", "p", "v")
            if cand is not None and abs(cand) < 20_000:
                last = cand
        # Volume: board totals — never treat indexsummary `v` as volume
        volume = _first_num(
            body,
            "tq",
            "tmq",
            "totalVol",
            "TotalVol",
            "accumulatedVolume",
            "nmVolume",
            "volume",
        )
        if is_trade_tick and volume is None:
            volume = _first_num(body, "v", "q")
        # ce/fl on indexsummary = advance/decline counts — not price ceiling/floor
        ceil = _positive_num(
            body.get("ceilingPrice") or body.get("Ceiling") or body.get("highLimit") or body.get("ceil")
        )
        floor = _positive_num(
            body.get("floorPrice") or body.get("Floor") or body.get("lowLimit") or body.get("floor")
        )
        high = _positive_num(body.get("high") or body.get("Highest") or body.get("h"))
        low = _positive_num(body.get("low") or body.get("Lowest") or body.get("l"))
        ref = _first_num(body, "ref", "refPrice", "basicPrice", "referencePrice", "tc")
    else:
        last = _first_num(
            body,
            "last",
            "LastPrice",
            "matchedPrice",
            "p",
            "price",
            "close",
        )
        # `v` on equity trade = accumulated session volume
        volume = _first_num(
            body,
            "volume",
            "v",
            "totalVol",
            "TotalVol",
            "accumulatedVolume",
            "nmVolume",
            "tq",
            "tmq",
        )
        ceil = _positive_num(
            body.get("ceilingPrice")
            or body.get("Ceiling")
            or body.get("highLimit")
            or body.get("ceil")
            or body.get("ce")
        )
        floor = _positive_num(
            body.get("floorPrice")
            or body.get("Floor")
            or body.get("lowLimit")
            or body.get("floor")
            or body.get("fl")
        )
        high = _positive_num(body.get("high") or body.get("Highest") or body.get("h"))
        low = _positive_num(body.get("low") or body.get("Lowest") or body.get("l"))
        # `o` observed as open/ref on equity trade ticks
        ref = _first_num(body, "ref", "refPrice", "basicPrice", "referencePrice", "tc", "o")

    if ref is None and last is not None and change is not None:
        ref = round(last - change, 6)
    if ref is None and last is not None and change_pct is not None and abs(change_pct) < 50:
        # cr is percent points (0.46 → 0.46%)
        ref = round(last / (1 + change_pct / 100.0), 6) if change_pct != -100 else last

    # Depth — explicit fields or SSI bids/asks arrays
    bid1 = _first_num(body, "bid1", "bidPrice1", "BestBid1", "g1")
    bid2 = _first_num(body, "bid2", "bidPrice2", "BestBid2")
    bid3 = _first_num(body, "bid3", "bidPrice3", "BestBid3")
    bidVol1 = _first_num(body, "bidVol1", "bidVolume1", "BestBidVol1")
    bidVol2 = _first_num(body, "bidVol2", "bidVolume2", "BestBidVol2")
    bidVol3 = _first_num(body, "bidVol3", "bidVolume3", "BestBidVol3")
    ask1 = _first_num(body, "ask1", "offer1", "offerPrice1", "BestOffer1")
    ask2 = _first_num(body, "ask2", "offer2", "offerPrice2", "BestOffer2")
    ask3 = _first_num(body, "ask3", "offer3", "offerPrice3", "BestOffer3")
    askVol1 = _first_num(body, "askVol1", "offerVol1", "offerVolume1", "BestOfferVol1")
    askVol2 = _first_num(body, "askVol2", "offerVol2", "offerVolume2", "BestOfferVol2")
    askVol3 = _first_num(body, "askVol3", "offerVol3", "offerVolume3", "BestOfferVol3")

    if bid1 is None and "bids" in body:
        bpx, bvol = _book_levels(body.get("bids"))
        if bpx:
            bid1, bid2, bid3 = (bpx + [None, None, None])[:3]
            bidVol1, bidVol2, bidVol3 = (bvol + [None, None, None])[:3]
    if ask1 is None and "asks" in body:
        apx, avol = _book_levels(body.get("asks"))
        if apx:
            ask1, ask2, ask3 = (apx + [None, None, None])[:3]
            askVol1, askVol2, askVol3 = (avol + [None, None, None])[:3]

    matchVol = _first_num(body, "matchVol", "lastVol", "matchedVol", "lot", "q")
    foreignBuy = _first_num(body, "foreignBuy", "fBuyVol", "BuyForeignQtty")
    foreignSell = _first_num(body, "foreignSell", "fSellVol", "SellForeignQtty")

    has_depth = any(x is not None for x in (bid1, ask1))
    has_extra = any(x is not None for x in (volume, matchVol, foreignBuy, foreignSell, high, low))
    if last is None and not has_depth and not has_extra:
        return None

    return {
        "symbol": sym,
        "kind": kind,
        "last": last,
        "ref": ref,
        "change": change,
        "change_pct": change_pct,
        "volume": volume,
        "high": high,
        "low": low,
        "ceil": ceil,
        "floor": floor,
        "bid1": bid1,
        "bid2": bid2,
        "bid3": bid3,
        "bidVol1": bidVol1,
        "bidVol2": bidVol2,
        "bidVol3": bidVol3,
        "ask1": ask1,
        "ask2": ask2,
        "ask3": ask3,
        "askVol1": askVol1,
        "askVol2": askVol2,
        "askVol3": askVol3,
        "matchVol": matchVol,
        "foreignBuy": foreignBuy,
        "foreignSell": foreignSell,
        "channel": channel or str(msg.get("type") or ""),
    }
