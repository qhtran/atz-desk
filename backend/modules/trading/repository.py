"""Data access for positions and transactions."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from backend.modules.trading.models import Position, TradeTransaction


def list_positions_for_user(db: Session, username: str) -> list[Position]:
    return (
        db.query(Position)
        .options(joinedload(Position.transactions))
        .filter(Position.username == username)
        .order_by(Position.symbol)
        .all()
    )


def get_position(db: Session, position_id: int, username: str) -> Position | None:
    return (
        db.query(Position)
        .options(joinedload(Position.transactions))
        .filter(Position.id == position_id, Position.username == username)
        .one_or_none()
    )


def get_open_position(db: Session, username: str, symbol: str) -> Position | None:
    return (
        db.query(Position)
        .options(joinedload(Position.transactions))
        .filter(
            Position.username == username,
            Position.symbol == symbol.upper(),
            Position.status == "open",
        )
        .one_or_none()
    )


def add_transaction(db: Session, tx: TradeTransaction) -> TradeTransaction:
    db.add(tx)
    db.flush()
    return tx
