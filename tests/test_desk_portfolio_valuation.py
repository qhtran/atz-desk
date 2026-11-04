"""Milestone 2 Phase 3–4: WAC ledger, unrealized/realized PnL, summary API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.desk_portfolio_store import (
    add_transaction,
    create_portfolio,
    init_desk_portfolio_store,
)
from backend.desk_portfolio_valuation import (
    build_cost_ledger,
    open_holdings_from_ledger,
    portfolio_summary,
    value_holdings,
)
from backend.main import app


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "desk_pf_val.db"
    init_desk_portfolio_store(path)
    return path


def test_wac_and_realized_pnl_partial_sell():
    txs = [
        {"id": 1, "symbol": "FPT", "side": "BUY", "quantity": 100, "price": 50_000, "fee": 0, "trade_date": "2026-01-01"},
        {"id": 2, "symbol": "FPT", "side": "BUY", "quantity": 100, "price": 60_000, "fee": 0, "trade_date": "2026-01-02"},
        {"id": 3, "symbol": "FPT", "side": "SELL", "quantity": 50, "price": 70_000, "fee": 1_000, "trade_date": "2026-01-03"},
    ]
    books, total_realized = build_cost_ledger(txs)
    # After 2 buys: qty=200, cost=5M+6M=11M, avg=55_000
    # Sell 50 @ 70k: realized = (70k-55k)*50 - 1000 = 750_000 - 1000
    assert books["FPT"].qty == pytest.approx(150)
    assert books["FPT"].cost_basis / books["FPT"].qty == pytest.approx(55_000)
    assert total_realized == pytest.approx(749_000)
    holdings = open_holdings_from_ledger(books)
    assert holdings[0]["avg_cost"] == pytest.approx(55_000)
    assert holdings[0]["qty"] == pytest.approx(150)


def test_buy_fee_in_cost_basis():
    txs = [
        {"id": 1, "symbol": "HPG", "side": "BUY", "quantity": 100, "price": 20_000, "fee": 5_000, "trade_date": "a"},
    ]
    books, _ = build_cost_ledger(txs)
    assert books["HPG"].cost_basis == pytest.approx(2_005_000)
    assert books["HPG"].cost_basis / books["HPG"].qty == pytest.approx(20_050)


def test_value_holdings_unrealized_and_weight():
    holdings = [
        {"symbol": "A", "qty": 10, "avg_cost": 100, "cost_basis": 1000, "realized_pnl": 0},
        {"symbol": "B", "qty": 5, "avg_cost": 200, "cost_basis": 1000, "realized_pnl": 50},
    ]
    prices = {"A": 110.0, "B": 180.0}
    rows, stock_mv, unreal = value_holdings(holdings, prices, total_value_for_weight=3000)
    assert stock_mv == pytest.approx(10 * 110 + 5 * 180)
    assert unreal == pytest.approx((110 - 100) * 10 + (180 - 200) * 5)
    assert rows[0]["unrealized_pnl"] == pytest.approx(100)
    assert rows[0]["weight_pct"] == pytest.approx(1100 / 3000 * 100, rel=1e-4)


def test_portfolio_summary_with_injected_prices(db: Path):
    p = create_portfolio("hoa", "Core", cash_balance=1_000_000, db_path=db)
    add_transaction(
        "hoa", p["id"], symbol="FPT", side="BUY", quantity=10, price=50_000, fee=0, db_path=db
    )
    add_transaction(
        "hoa", p["id"], symbol="FPT", side="SELL", quantity=4, price=55_000, fee=0, db_path=db
    )
    summary = portfolio_summary(
        "hoa",
        p["id"],
        prices={"FPT": 60_000},
        db_path=db,
    )
    assert summary is not None
    # Remaining qty 6, avg still 50_000 (single buy lot), MV=360_000
    assert summary["realized_pnl"] == pytest.approx((55_000 - 50_000) * 4)
    assert summary["holdings"][0]["qty"] == pytest.approx(6)
    assert summary["holdings"][0]["avg_cost"] == pytest.approx(50_000)
    assert summary["holdings"][0]["unrealized_pnl"] == pytest.approx((60_000 - 50_000) * 6)
    assert summary["stock_market_value"] == pytest.approx(360_000)
    # cash after buy 1M-500k=500k; after sell +220k = 720k
    assert summary["cash_balance"] == pytest.approx(720_000)
    assert summary["total_value"] == pytest.approx(720_000 + 360_000)
    assert summary["unrealized_pnl"] == pytest.approx(60_000)


def test_api_summary_auth_and_payload(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_sum.db"
    import backend.desk_portfolio_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_portfolio_store(path)
    client = TestClient(app)
    assert client.get("/api/portfolios/1/summary").status_code == 401

    headers = {"X-Authentik-Username": "hoa", "X-Authentik-Groups": "members"}
    created = client.post(
        "/api/portfolios",
        headers=headers,
        json={"name": "Core", "cash_balance": 5_000_000},
    )
    assert created.status_code == 201
    pid = created.json()["item"]["id"]
    client.post(
        f"/api/portfolios/{pid}/transactions",
        headers=headers,
        json={"symbol": "VNM", "side": "BUY", "quantity": 10, "price": 100_000},
    )

    # Inject prices via monkeypatch on load_priceboard_prices
    import backend.desk_portfolio_valuation as val

    monkeypatch.setattr(val, "load_priceboard_prices", lambda syms, **kw: {"VNM": 105_000.0})
    res = client.get(f"/api/portfolios/{pid}/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["portfolio_id"] == pid
    assert body["unrealized_pnl"] == pytest.approx(50_000)
    assert body["holdings"][0]["symbol"] == "VNM"
    assert body["holdings"][0]["weight_pct"] is not None
    assert client.get(f"/api/portfolios/{pid}/summary", headers={"X-Authentik-Username": "bob"}).status_code == 404
