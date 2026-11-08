"""Morning brief public + admin HTTP routes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.morning_brief import generate_morning_brief
from backend.morning_brief_store import (
    delete_watch_item,
    get_brief_by_date,
    get_config,
    get_latest_brief,
    list_watchbook,
    put_config,
    replace_watchbook,
    upsert_watch_item,
)
from backend.portfolio_quotes import DEFAULT_BARS_DIR


class WatchItemBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(min_length=1, max_length=16)
    buy_price: float | None = None
    buy_date: str | None = None
    stop_loss: float | None = None
    resistance: float | None = None
    status: str | None = "giu"
    note: str | None = None


class WatchbookReplaceBody(BaseModel):
    items: list[WatchItemBody] = Field(default_factory=list)


class BriefConfigBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    timezone: str | None = None
    title_template: str | None = None
    index_symbols: list[str] | None = None
    sector_theme_ids: list[str] | None = None
    tech_symbols: list[str] | None = None


def register_brief_routes(
    app,
    *,
    require_admin: Callable[[Request], str],
) -> None:
    """Attach ``/api/briefs*`` and ``/api/admin/briefs*``."""

    @app.get("/api/briefs/latest")
    async def briefs_latest() -> dict[str, Any]:
        item = await asyncio.to_thread(get_latest_brief)
        if item is None:
            raise HTTPException(status_code=404, detail="ERR-BRIEF-020: no brief yet")
        return {"ok": True, "brief": item}

    @app.get("/api/briefs")
    async def briefs_by_date(date: str | None = None) -> dict[str, Any]:
        if not date:
            item = await asyncio.to_thread(get_latest_brief)
        else:
            item = await asyncio.to_thread(get_brief_by_date, date.strip())
        if item is None:
            raise HTTPException(status_code=404, detail="ERR-BRIEF-020: brief not found")
        return {"ok": True, "brief": item}

    @app.get("/api/admin/briefs/config")
    async def admin_briefs_config(request: Request) -> dict[str, Any]:
        require_admin(request)
        return {"ok": True, "config": await asyncio.to_thread(get_config)}

    @app.put("/api/admin/briefs/config")
    async def admin_briefs_config_put(request: Request, body: BriefConfigBody) -> dict[str, Any]:
        require_admin(request)
        payload = body.model_dump(exclude_none=True)
        try:
            cfg = await asyncio.to_thread(put_config, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "config": cfg}

    @app.get("/api/admin/briefs/watchbook")
    async def admin_watchbook_get(request: Request) -> dict[str, Any]:
        require_admin(request)
        items = await asyncio.to_thread(list_watchbook)
        return {"ok": True, "items": items}

    @app.put("/api/admin/briefs/watchbook")
    async def admin_watchbook_put(request: Request, body: WatchbookReplaceBody) -> dict[str, Any]:
        require_admin(request)
        raw = [item.model_dump() for item in body.items]
        try:
            items = await asyncio.to_thread(replace_watchbook, raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "items": items}

    @app.post("/api/admin/briefs/watchbook")
    async def admin_watchbook_post(request: Request, body: WatchItemBody) -> dict[str, Any]:
        require_admin(request)
        try:
            item = await asyncio.to_thread(
                upsert_watch_item,
                symbol=body.symbol,
                buy_price=body.buy_price,
                buy_date=body.buy_date,
                stop_loss=body.stop_loss,
                resistance=body.resistance,
                status=body.status,
                note=body.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "item": item}

    @app.delete("/api/admin/briefs/watchbook/{item_id}")
    async def admin_watchbook_delete(request: Request, item_id: int) -> dict[str, Any]:
        require_admin(request)
        ok = await asyncio.to_thread(delete_watch_item, item_id)
        if not ok:
            raise HTTPException(status_code=404, detail="ERR-BRIEF-004: watch item not found")
        return {"ok": True}

    @app.post("/api/admin/briefs/run")
    async def admin_briefs_run(request: Request) -> dict[str, Any]:
        """Manual generate (does not replace host cron)."""
        require_admin(request)
        bars = Path(DEFAULT_BARS_DIR)

        def _run() -> dict[str, Any]:
            return generate_morning_brief(bars_dir=bars)

        try:
            brief = await asyncio.to_thread(_run)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"ERR-BRIEF-000: {exc}") from exc
        return {"ok": True, "brief": brief}
