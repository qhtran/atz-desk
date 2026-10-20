"""Priceboard tick JSON contract shared by mock + SSI live workers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TZ_VN = timezone(timedelta(hours=7))


def now_iso() -> str:
    return datetime.now(TZ_VN).isoformat()


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ceil_floor(ref: float, kind: str) -> tuple[float | int, float | int]:
    if kind == "index":
        return round(ref * 1.07, 2), round(ref * 0.93, 2)
    r = int(round(ref))
    return int(round(r * 1.07 / 50) * 50), int(round(r * 0.93 / 50) * 50)


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
    """Best-effort map SSI WS payload → kwargs for build_tick. None = ignore."""
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

    indexes = {"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"}
    kind = "index" if sym in indexes else "equity"

    last = _num(
        body.get("last")
        or body.get("LastPrice")
        or body.get("matchedPrice")
        or body.get("close")
        or body.get("c")
        or body.get("p")
        or body.get("price")
        or body.get("indexValue")
        or body.get("IndexValue")
        or body.get("value")
    )
    if last is None:
        return None

    ref = _num(
        body.get("ref")
        or body.get("refPrice")
        or body.get("basicPrice")
        or body.get("referencePrice")
        or body.get("tc")
    )
    change = _num(body.get("change") or body.get("priceChange") or body.get("indexChange") or body.get("Change"))
    change_pct = _num(
        body.get("change_pct")
        or body.get("changePercent")
        or body.get("ratioChange")
        or body.get("indexChangePercentage")
    )
    volume = _num(
        body.get("volume")
        or body.get("totalVol")
        or body.get("TotalVol")
        or body.get("accumulatedVolume")
        or body.get("nmVolume")
    )
    high = _num(body.get("high") or body.get("Highest") or body.get("h"))
    low = _num(body.get("low") or body.get("Lowest") or body.get("l"))
    ceil = _num(body.get("ceil") or body.get("ceiling") or body.get("ceilingPrice") or body.get("highLimit"))
    floor = _num(body.get("floor") or body.get("floorPrice") or body.get("lowLimit"))

    # Depth — SSI quote often bid/offer 1..3
    bid1 = _num(body.get("bid1") or body.get("bidPrice1") or body.get("BestBid1") or body.get("g1"))
    bid2 = _num(body.get("bid2") or body.get("bidPrice2") or body.get("BestBid2"))
    bid3 = _num(body.get("bid3") or body.get("bidPrice3") or body.get("BestBid3"))
    bidVol1 = _num(body.get("bidVol1") or body.get("bidVolume1") or body.get("BestBidVol1"))
    bidVol2 = _num(body.get("bidVol2") or body.get("bidVolume2") or body.get("BestBidVol2"))
    bidVol3 = _num(body.get("bidVol3") or body.get("bidVolume3") or body.get("BestBidVol3"))
    ask1 = _num(body.get("ask1") or body.get("offer1") or body.get("offerPrice1") or body.get("BestOffer1"))
    ask2 = _num(body.get("ask2") or body.get("offer2") or body.get("offerPrice2") or body.get("BestOffer2"))
    ask3 = _num(body.get("ask3") or body.get("offer3") or body.get("offerPrice3") or body.get("BestOffer3"))
    askVol1 = _num(body.get("askVol1") or body.get("offerVol1") or body.get("offerVolume1") or body.get("BestOfferVol1"))
    askVol2 = _num(body.get("askVol2") or body.get("offerVol2") or body.get("offerVolume2") or body.get("BestOfferVol2"))
    askVol3 = _num(body.get("askVol3") or body.get("offerVol3") or body.get("offerVolume3") or body.get("BestOfferVol3"))
    matchVol = _num(body.get("matchVol") or body.get("lastVol") or body.get("matchedVol") or body.get("lot"))
    foreignBuy = _num(body.get("foreignBuy") or body.get("fBuyVol") or body.get("BuyForeignQtty"))
    foreignSell = _num(body.get("foreignSell") or body.get("fSellVol") or body.get("SellForeignQtty"))

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
