"""Catalog + quote snapshot + on-demand watch APIs (Core + On-Demand)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.market_catalog import get_catalog_symbol, search_catalog
from backend.ondemand_watch import list_active_ondemand, touch_ondemand_symbols
from backend.quote_snapshot import resolve_quote_snapshots

router = APIRouter(tags=["catalog"])


class PriceboardWatchBody(BaseModel):
    symbols: list[str] = Field(default_factory=list)


@router.get("/api/catalog/symbols")
async def catalog_symbols(
    q: str = Query(default="", max_length=32),
    limit: int = Query(default=12, ge=1, le=50),
) -> dict[str, Any]:
    """Search master catalog for Quick Switcher / watchlist add."""
    items = search_catalog(q, limit=limit)
    return {
        "ok": True,
        "q": str(q or "").strip().upper(),
        "count": len(items),
        "items": items,
    }


@router.get("/api/catalog/symbol/{symbol}")
async def catalog_symbol_one(symbol: str) -> dict[str, Any]:
    item = get_catalog_symbol(symbol)
    if not item:
        return {"ok": False, "symbol": str(symbol or "").upper(), "item": None}
    return {"ok": True, "item": item}


@router.get("/api/quotes/snapshot")
async def quotes_snapshot(
    symbols: str = Query(default="", max_length=512),
) -> dict[str, Any]:
    """Static/snapshot quotes — Redis → OHLCV → catalog stub (no SSI WS subscribe)."""
    return resolve_quote_snapshots(symbols)


@router.post("/api/priceboard/watch")
async def priceboard_watch(body: PriceboardWatchBody) -> dict[str, Any]:
    """Touch off-core symbols so SSI worker dynamically SUBSCRIBE (idle unsubscribe)."""
    return touch_ondemand_symbols(body.symbols)


@router.get("/api/priceboard/ondemand")
async def priceboard_ondemand() -> dict[str, Any]:
    """Debug/ops: active on-demand symbols (non-expired)."""
    items = list_active_ondemand()
    return {"ok": True, "count": len(items), "symbols": items}
