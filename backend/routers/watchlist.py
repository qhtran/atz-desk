"""Personal watchlist CRUD — ``/api/user/watchlists`` (Authentik / desk session)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.desk_session import COOKIE_NAME as DESK_COOKIE
from backend.identity import resolve_request_identity as resolve_me
from backend.ondemand_watch import touch_ondemand_symbols
from backend.watchlist_store import (
    create_watchlist,
    delete_watchlist,
    list_watchlists,
    update_watchlist,
)

router = APIRouter(prefix="/api/user", tags=["watchlists"])


class WatchlistCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    symbols: list[str] = Field(default_factory=list)


class WatchlistUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    symbols: list[str] | None = None


def _require_user(request: Request) -> str:
    me = resolve_me(request.headers, desk_cookie=request.cookies.get(DESK_COOKIE))
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    return str(me["username"])


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["name"],
        "symbols": list(item.get("symbols") or []),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


@router.get("/watchlists")
def api_list_watchlists(request: Request) -> dict:
    user = _require_user(request)
    items = list_watchlists(user)
    return {"ok": True, "items": [_public(i) for i in items]}


@router.post("/watchlists", status_code=201)
def api_create_watchlist(request: Request, body: WatchlistCreateBody) -> dict:
    user = _require_user(request)
    try:
        item = create_watchlist(user, body.name, body.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    touch_ondemand_symbols(list(item.get("symbols") or []))
    return {"ok": True, "item": _public(item)}


@router.put("/watchlists/{watchlist_id}")
def api_update_watchlist(
    watchlist_id: int,
    request: Request,
    body: WatchlistUpdateBody,
) -> dict:
    user = _require_user(request)
    if body.name is None and body.symbols is None:
        raise HTTPException(status_code=400, detail="name or symbols required")
    try:
        item = update_watchlist(
            user,
            watchlist_id,
            name=body.name,
            symbols=body.symbols,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    touch_ondemand_symbols(list(item.get("symbols") or []))
    return {"ok": True, "item": _public(item)}


@router.delete("/watchlists/{watchlist_id}")
def api_delete_watchlist(watchlist_id: int, request: Request) -> dict:
    user = _require_user(request)
    ok = delete_watchlist(user, watchlist_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return {"ok": True, "deleted": watchlist_id}
