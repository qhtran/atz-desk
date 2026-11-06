"""Portfolio + transaction CRUD — ``/api/portfolios`` (Desk Session / ForwardAuth)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.desk_portfolio_store import (
    add_transaction,
    create_portfolio,
    delete_portfolio,
    list_portfolios,
    list_positions,
    list_transactions,
)
from backend.desk_portfolio_valuation import portfolio_summary
from backend.desk_session import COOKIE_NAME as DESK_COOKIE
from backend.identity import resolve_request_identity as resolve_me

router = APIRouter(prefix="/api/portfolios", tags=["desk-portfolios"])


class PortfolioCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=512)
    cash_balance: float = Field(default=0.0, ge=0)
    is_default: bool = False


class TransactionCreateBody(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    side: str = Field(..., min_length=3, max_length=4)
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    fee: float = Field(default=0.0, ge=0)
    trade_date: str | None = None
    notes: str = Field(default="", max_length=512)

    @field_validator("symbol")
    @classmethod
    def _symbol_upper(cls, v: str) -> str:
        s = str(v or "").strip().upper()
        if not s:
            raise ValueError("symbol required")
        return s

    @field_validator("side")
    @classmethod
    def _side_upper(cls, v: str) -> str:
        s = str(v or "").strip().upper()
        if s not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        return s


def _require_user(request: Request) -> str:
    me = resolve_me(request.headers, desk_cookie=request.cookies.get(DESK_COOKIE))
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    return str(me["username"])


def _public_portfolio(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item.get("description") or "",
        "cash_balance": item.get("cash_balance", 0),
        "is_default": bool(item.get("is_default")),
        "created_at": item.get("created_at"),
    }


def _public_tx(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "portfolio_id": item["portfolio_id"],
        "symbol": item["symbol"],
        "side": item["side"],
        "quantity": item["quantity"],
        "price": item["price"],
        "fee": item.get("fee", 0),
        "trade_date": item.get("trade_date"),
        "notes": item.get("notes") or "",
    }


@router.get("")
@router.get("/")
def api_list_portfolios(request: Request) -> dict:
    user = _require_user(request)
    items = list_portfolios(user)
    return {"ok": True, "items": [_public_portfolio(i) for i in items]}


@router.post("", status_code=201)
@router.post("/", status_code=201)
def api_create_portfolio(request: Request, body: PortfolioCreateBody) -> dict:
    user = _require_user(request)
    try:
        item = create_portfolio(
            user,
            body.name,
            description=body.description,
            cash_balance=body.cash_balance,
            is_default=body.is_default,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": _public_portfolio(item)}


@router.delete("/{portfolio_id}")
def api_delete_portfolio(portfolio_id: int, request: Request) -> dict:
    user = _require_user(request)
    ok = delete_portfolio(user, portfolio_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"ok": True, "deleted": portfolio_id}


@router.get("/{portfolio_id}/summary")
def api_portfolio_summary(portfolio_id: int, request: Request) -> dict:
    """Cash + stock MV, unrealized/realized PnL, per-symbol weights (live Redis last)."""
    user = _require_user(request)
    summary = portfolio_summary(user, portfolio_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"ok": True, **summary}


@router.get("/{portfolio_id}/transactions")
def api_list_transactions(portfolio_id: int, request: Request) -> dict:
    user = _require_user(request)
    items = list_transactions(user, portfolio_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"ok": True, "items": [_public_tx(i) for i in items]}


@router.post("/{portfolio_id}/transactions", status_code=201)
def api_add_transaction(
    portfolio_id: int,
    request: Request,
    body: TransactionCreateBody,
) -> dict:
    user = _require_user(request)
    try:
        item = add_transaction(
            user,
            portfolio_id,
            symbol=body.symbol,
            side=body.side,
            quantity=body.quantity,
            price=body.price,
            fee=body.fee,
            trade_date=body.trade_date,
            notes=body.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Portfolio not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    folio_items = list_portfolios(user)
    cash = next((p["cash_balance"] for p in folio_items if p["id"] == portfolio_id), None)
    positions = list_positions(portfolio_id)
    return {
        "ok": True,
        "item": _public_tx(item),
        "cash_balance": cash,
        "positions": positions,
    }
