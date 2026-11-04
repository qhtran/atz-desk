"""Personal price alert CRUD — ``/api/alerts`` (Desk Session / ForwardAuth)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.desk_alerts_store import (
    create_alert_config,
    deactivate_alert_config,
    list_alert_configs,
)
from backend.desk_session import COOKIE_NAME as DESK_COOKIE
from backend.identity import resolve_me

router = APIRouter(prefix="/api/alerts", tags=["desk-alerts"])


class AlertCreateBody(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    condition: Literal["GT", "LT"]
    target_value: float = Field(..., gt=0)

    @field_validator("symbol")
    @classmethod
    def _symbol_upper(cls, v: str) -> str:
        s = str(v or "").strip().upper()
        if not s:
            raise ValueError("symbol required")
        return s


def _require_user(request: Request) -> str:
    me = resolve_me(request.headers, desk_cookie=request.cookies.get(DESK_COOKIE))
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    return str(me["username"])


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "symbol": item["symbol"],
        "condition": item["condition"],
        "target_value": item["target_value"],
        "is_active": item["is_active"],
        "created_at": item.get("created_at"),
    }


@router.get("")
@router.get("/")
def api_list_alerts(request: Request) -> dict:
    user = _require_user(request)
    items = list_alert_configs(user, active_only=True)
    return {"ok": True, "items": [_public(i) for i in items]}


@router.post("", status_code=201)
@router.post("/", status_code=201)
def api_create_alert(request: Request, body: AlertCreateBody) -> dict:
    user = _require_user(request)
    try:
        item = create_alert_config(
            user,
            symbol=body.symbol,
            condition=body.condition,
            target_value=body.target_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": _public(item)}


@router.delete("/{alert_id}")
def api_delete_alert(alert_id: int, request: Request) -> dict:
    user = _require_user(request)
    item = deactivate_alert_config(user, alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"ok": True, "deactivated": alert_id, "item": _public(item)}
