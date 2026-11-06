"""FastAPI router /api/trading."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.trading_config import load_trading_config
from backend.desk_session import COOKIE_NAME as DESK_COOKIE
from backend.identity import resolve_request_identity as resolve_me
from backend.modules.trading.schemas import BuyRequest, LevelsPatch, SellRequest
from backend.modules.trading import service

router = APIRouter(prefix="/api/trading", tags=["trading"])


def _trading_user(request: Request) -> str:
    me = resolve_me(request.headers, desk_cookie=request.cookies.get(DESK_COOKIE))
    if me and me.get("username"):
        return str(me["username"])
    return str(load_trading_config().get("default_user", "default_user"))


@router.get("/positions")
def api_list_positions(request: Request, db: Session = Depends(get_db)) -> dict:
    user = _trading_user(request)
    items = service.list_positions(db, user)
    return {"ok": True, "positions": [p.model_dump() for p in items]}


@router.get("/positions/{position_id}")
def api_get_position(position_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = _trading_user(request)
    detail = service.get_position_detail(db, user, position_id)
    return {"ok": True, "position": detail.model_dump()}


@router.post("/buy")
def api_buy(body: BuyRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = _trading_user(request)
    view = service.record_buy(db, user, body)
    return {"ok": True, "position": view.model_dump()}


@router.post("/sell")
def api_sell(body: SellRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user = _trading_user(request)
    view = service.record_sell(db, user, body)
    return {"ok": True, "position": view.model_dump()}


@router.patch("/positions/{position_id}/levels")
def api_patch_levels(
    position_id: int,
    body: LevelsPatch,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = _trading_user(request)
    view = service.patch_levels(db, user, position_id, body)
    return {"ok": True, "position": view.model_dump()}


@router.post("/positions/{position_id}/close")
def api_close_position(
    position_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = _trading_user(request)
    view = service.close_position(db, user, position_id)
    return {"ok": True, "position": view.model_dump()}
