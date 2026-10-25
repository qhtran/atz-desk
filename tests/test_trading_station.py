"""Trạm Trading service — avg, fee, tax, tranche."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from backend.core.database import get_session_factory, init_db, reset_engine
from backend.core.errors import AppError
from backend.core.trading_config import load_trading_config
from backend.modules.trading.schemas import BuyRequest, SellRequest
from backend.modules.trading import service


@pytest.fixture()
def trading_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test_trading.db"
    monkeypatch.setenv("TRADING_DB_PATH", str(db_file))
    load_trading_config.cache_clear()
    reset_engine()
    init_db(db_file)
    factory = get_session_factory(db_file)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        reset_engine()
        load_trading_config.cache_clear()


def test_avg_after_two_buys(trading_db: Session) -> None:
    user = "u1"
    service.record_buy(
        trading_db,
        user,
        BuyRequest(symbol="HPG", tranche=1, qty=100, price=20000),
    )
    view = service.record_buy(
        trading_db,
        user,
        BuyRequest(symbol="HPG", tranche=2, qty=100, price=22000),
    )
    assert view.qty == 200
    assert view.avg == 21000.0
    assert view.tranches[0].t == 1
    assert view.tranches[1].t == 2


def test_duplicate_tranche_rejected(trading_db: Session) -> None:
    user = "u2"
    service.record_buy(
        trading_db,
        user,
        BuyRequest(symbol="FPT", tranche=1, qty=50, price=100000),
    )
    with pytest.raises(AppError):
        service.record_buy(
            trading_db,
            user,
            BuyRequest(symbol="FPT", tranche=1, qty=10, price=99000),
        )


def test_sell_applies_tax(trading_db: Session) -> None:
    user = "u3"
    service.record_buy(
        trading_db,
        user,
        BuyRequest(symbol="VCB", tranche=1, qty=100, price=50000),
    )
    before = service.list_positions(trading_db, user)[0]
    sold = service.record_sell(
        trading_db,
        user,
        SellRequest(symbol="VCB", qty=50, price=52000),
    )
    assert sold.qty == 50
    gross = 50 * 52000
    expected_tax = round(gross * 0.001, 2)
    detail = service.get_position_detail(trading_db, user, sold.id)
    sell_tx = [t for t in detail.transactions if t.side == "SELL"][0]
    assert sell_tx.tax == expected_tax
    assert sell_tx.fee == round(gross * 0.0015, 2)
    assert sold.qty == before.qty - 50
