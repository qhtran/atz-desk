"""Trạm Trading business logic."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.errors import AppError, ERR_TS_BUSINESS, ERR_TS_NOT_FOUND
from backend.core.redis_client import get_last_price
from backend.core.trading_config import load_trading_config
from backend.modules.trading.models import Position, TradeTransaction
from backend.modules.trading import repository as repo
from backend.modules.trading.schemas import (
    BuyRequest,
    LevelsPatch,
    PositionDetail,
    PositionView,
    SellRequest,
    TransactionView,
    TrancheRow,
)


def _cfg() -> dict:
    return load_trading_config()


def _fee_rate() -> float:
    return float(_cfg().get("brokerage_fee_rate", 0.0015))


def _tax_rate() -> float:
    return float(_cfg().get("sell_tax_rate", 0.001))


def _max_tranche() -> int:
    return int(_cfg().get("max_tranche", 5))


def _parse_tp(raw: str) -> list[float]:
    try:
        data = json.loads(raw or "[]")
        return [float(x) for x in data if x is not None]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _dump_tp(values: list[float]) -> str:
    return json.dumps([float(x) for x in values])


def _used_tranches(position: Position) -> set[int]:
    used: set[int] = set()
    for tx in position.transactions:
        if tx.side == "BUY" and tx.tranche is not None:
            used.add(int(tx.tranche))
    return used


def _alert_state(last: float | None, sl: float | None, tp: list[float]) -> str:
    if last is None:
        return "idle"
    if sl is not None and last <= sl:
        return "sl"
    for level in sorted(tp):
        if last >= level:
            return "tp"
    return "idle"


def _position_view(position: Position, last: float | None) -> PositionView:
    qty = float(position.qty or 0)
    avg = float(position.avg_buy_price or 0)
    invested = float(position.invested or 0)
    mv = qty * last if last is not None and qty > 0 else 0.0
    cost_basis = qty * avg if qty > 0 else 0.0
    unrealized = mv - cost_basis if qty > 0 and last is not None else 0.0
    pnl = float(position.realized_pnl or 0) + unrealized
    pnl_pct = (unrealized / cost_basis * 100.0) if cost_basis > 0 and qty > 0 else 0.0
    tp = _parse_tp(position.tp_json)
    tranches: list[TrancheRow] = []
    for tx in position.transactions:
        if tx.side == "BUY" and tx.tranche is not None:
            tranches.append(
                TrancheRow(t=int(tx.tranche), qty=tx.qty, price=tx.price, fee=tx.fee)
            )
    return PositionView(
        id=position.id,
        symbol=position.symbol,
        qty=qty,
        avg=avg,
        last=last,
        invested=invested,
        mv=mv,
        pnl=pnl,
        pnlPct=round(pnl_pct, 4),
        sl=position.sl,
        tp=tp,
        alert=_alert_state(last, position.sl, tp),
        status=position.status,
        tranches=tranches,
    )


def list_positions(db: Session, username: str) -> list[PositionView]:
    cfg = _cfg()
    rows = repo.list_positions_for_user(db, username)
    views: list[PositionView] = []
    for pos in rows:
        last = None
        if pos.status == "open" and pos.qty > 0:
            last = get_last_price(
                pos.symbol,
                hash_key=str(cfg.get("redis_hash", "priceboard:quotes")),
                field=str(cfg.get("quote_field", "last")),
            )
        views.append(_position_view(pos, last))
    return views


def get_position_detail(db: Session, username: str, position_id: int) -> PositionDetail:
    pos = repo.get_position(db, position_id, username)
    if not pos:
        raise AppError("Position not found", error_code=ERR_TS_NOT_FOUND, status_code=404)
    cfg = _cfg()
    last = get_last_price(
        pos.symbol,
        hash_key=str(cfg.get("redis_hash", "priceboard:quotes")),
        field=str(cfg.get("quote_field", "last")),
    ) if pos.qty > 0 else None
    base = _position_view(pos, last)
    txs = [
        TransactionView(
            id=tx.id,
            side=tx.side,
            tranche=tx.tranche,
            qty=tx.qty,
            price=tx.price,
            fee=tx.fee,
            tax=tx.tax,
            executed_at=tx.executed_at,
            note=tx.note or "",
        )
        for tx in pos.transactions
    ]
    return PositionDetail(**base.model_dump(), transactions=txs)


def record_buy(db: Session, username: str, body: BuyRequest) -> PositionView:
    symbol = body.symbol.strip().upper()
    if not symbol:
        raise AppError("Symbol required", error_code=ERR_TS_BUSINESS)
    tranche = int(body.tranche)
    if tranche < 1 or tranche > _max_tranche():
        raise AppError(f"Tranche must be 1..{_max_tranche()}", error_code=ERR_TS_BUSINESS)

    pos = repo.get_open_position(db, username, symbol)
    if pos is None:
        pos = Position(username=username, symbol=symbol, status="open")
        db.add(pos)
        db.flush()
    elif pos.status != "open":
        raise AppError("Position is closed", error_code=ERR_TS_BUSINESS)

    used = _used_tranches(pos)
    if tranche in used:
        raise AppError(f"Tranche T{tranche} already used", error_code=ERR_TS_BUSINESS)
    if len(used) >= _max_tranche() and tranche not in used:
        raise AppError(f"Max {_max_tranche()} tranches per symbol", error_code=ERR_TS_BUSINESS)

    gross = body.qty * body.price
    fee = round(gross * _fee_rate(), 2)
    old_qty = float(pos.qty or 0)
    old_avg = float(pos.avg_buy_price or 0)
    new_qty = old_qty + body.qty
    if new_qty <= 0:
        raise AppError("Invalid quantity", error_code=ERR_TS_BUSINESS)
    new_avg = (
        (old_qty * old_avg + body.qty * body.price) / new_qty if old_qty > 0 else body.price
    )
    pos.qty = new_qty
    pos.avg_buy_price = round(new_avg, 4)
    pos.invested = round(float(pos.invested or 0) + gross + fee, 2)
    pos.updated_at = datetime.now(timezone.utc)

    tx = TradeTransaction(
        position_id=pos.id,
        side="BUY",
        tranche=tranche,
        qty=body.qty,
        price=body.price,
        fee=fee,
        tax=0.0,
        note=body.note or "",
    )
    repo.add_transaction(db, tx)
    db.commit()
    db.refresh(pos)
    cfg = _cfg()
    last = get_last_price(
        symbol,
        hash_key=str(cfg.get("redis_hash", "priceboard:quotes")),
        field=str(cfg.get("quote_field", "last")),
    )
    return _position_view(pos, last)


def record_sell(db: Session, username: str, body: SellRequest) -> PositionView:
    symbol = body.symbol.strip().upper()
    pos = repo.get_open_position(db, username, symbol)
    if not pos or float(pos.qty or 0) <= 0:
        raise AppError("No open position", error_code=ERR_TS_NOT_FOUND, status_code=404)
    if body.qty > float(pos.qty):
        raise AppError("Sell qty exceeds position", error_code=ERR_TS_BUSINESS)

    gross = body.qty * body.price
    fee = round(gross * _fee_rate(), 2)
    tax = round(gross * _tax_rate(), 2)
    avg = float(pos.avg_buy_price or 0)
    realized_delta = (body.price - avg) * body.qty - fee - tax
    pos.realized_pnl = round(float(pos.realized_pnl or 0) + realized_delta, 2)
    pos.qty = round(float(pos.qty) - body.qty, 6)
    if pos.qty <= 0:
        pos.qty = 0
        pos.status = "closed"
        pos.avg_buy_price = 0
    pos.invested = round(max(0.0, float(pos.invested or 0) - body.qty * avg), 2)
    pos.updated_at = datetime.now(timezone.utc)

    tx = TradeTransaction(
        position_id=pos.id,
        side="SELL",
        tranche=None,
        qty=body.qty,
        price=body.price,
        fee=fee,
        tax=tax,
        note=body.note or "",
    )
    repo.add_transaction(db, tx)
    db.commit()
    db.refresh(pos)
    cfg = _cfg()
    last = get_last_price(
        symbol,
        hash_key=str(cfg.get("redis_hash", "priceboard:quotes")),
        field=str(cfg.get("quote_field", "last")),
    ) if pos.qty > 0 else None
    return _position_view(pos, last)


def patch_levels(db: Session, username: str, position_id: int, body: LevelsPatch) -> PositionView:
    pos = repo.get_position(db, position_id, username)
    if not pos:
        raise AppError("Position not found", error_code=ERR_TS_NOT_FOUND, status_code=404)
    if body.sl is not None:
        pos.sl = body.sl
    if body.tp is not None:
        pos.tp_json = _dump_tp(body.tp)
    pos.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pos)
    cfg = _cfg()
    last = get_last_price(
        pos.symbol,
        hash_key=str(cfg.get("redis_hash", "priceboard:quotes")),
        field=str(cfg.get("quote_field", "last")),
    ) if pos.qty > 0 else None
    return _position_view(pos, last)


def close_position(db: Session, username: str, position_id: int) -> PositionView:
    pos = repo.get_position(db, position_id, username)
    if not pos:
        raise AppError("Position not found", error_code=ERR_TS_NOT_FOUND, status_code=404)
    pos.status = "closed"
    pos.qty = 0
    pos.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pos)
    return _position_view(pos, None)
