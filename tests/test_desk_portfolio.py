"""Milestone 2 Phase 1–2: desk portfolios + transactions SQLite + /api/portfolios."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.desk_portfolio_store import (
    add_transaction,
    create_portfolio,
    delete_portfolio,
    delete_transaction,
    init_desk_portfolio_store,
    list_portfolios,
    list_positions,
    list_transactions,
    position_qty,
)
from backend.main import app


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "desk_portfolio.db"
    init_desk_portfolio_store(path)
    return path


def test_create_list_delete_portfolio_isolated(db: Path):
    a = create_portfolio("alice", "Core", cash_balance=10_000_000, is_default=True, db_path=db)
    b = create_portfolio("bob", "Banks", cash_balance=1_000_000, db_path=db)
    assert a["is_default"] is True
    assert a["cash_balance"] == 10_000_000
    assert list_portfolios("alice", db_path=db)[0]["id"] == a["id"]
    assert list_portfolios("bob", db_path=db)[0]["id"] == b["id"]

    # second default clears previous
    a2 = create_portfolio("alice", "Sat", is_default=True, db_path=db)
    alice = {p["id"]: p for p in list_portfolios("alice", db_path=db)}
    assert alice[a2["id"]]["is_default"] is True
    assert alice[a["id"]]["is_default"] is False

    assert delete_portfolio("bob", a["id"], db_path=db) is False
    assert delete_portfolio("alice", a["id"], db_path=db) is True
    get_ids = {p["id"] for p in list_portfolios("alice", db_path=db)}
    assert a["id"] not in get_ids
    assert a2["id"] in get_ids


def test_buy_sell_updates_cash_and_qty(db: Path):
    start_cash = 10_000_000
    p = create_portfolio("hoa", "Main", cash_balance=start_cash, db_path=db)
    pid = p["id"]

    buy = add_transaction(
        "hoa",
        pid,
        symbol="fpt",
        side="BUY",
        quantity=100,
        price=50_000,
        fee=1_000,
        db_path=db,
    )
    assert buy["symbol"] == "FPT"
    assert buy["side"] == "BUY"
    cash_after_buy = list_portfolios("hoa", db_path=db)[0]["cash_balance"]
    assert cash_after_buy == pytest.approx(start_cash - 5_000_000 - 1_000)
    assert position_qty(pid, "FPT", db_path=db) == 100
    assert list_positions(pid, db_path=db)[0]["avg"] == pytest.approx(50_000)

    sell = add_transaction(
        "hoa",
        pid,
        symbol="FPT",
        side="SELL",
        quantity=40,
        price=52_000,
        fee=500,
        db_path=db,
    )
    assert sell["side"] == "SELL"
    cash_after_sell = list_portfolios("hoa", db_path=db)[0]["cash_balance"]
    assert cash_after_sell == pytest.approx(cash_after_buy + 40 * 52_000 - 500)
    assert position_qty(pid, "FPT", db_path=db) == 60

    txs = list_transactions("hoa", pid, db_path=db)
    assert txs is not None and len(txs) == 2


def test_rejects_bad_qty_price_and_overtrade(db: Path):
    p = create_portfolio("hoa", "Main", cash_balance=100_000, db_path=db)
    pid = p["id"]

    with pytest.raises(ValueError, match="quantity"):
        add_transaction("hoa", pid, symbol="FPT", side="BUY", quantity=0, price=10, db_path=db)
    with pytest.raises(ValueError, match="price"):
        add_transaction("hoa", pid, symbol="FPT", side="BUY", quantity=1, price=0, db_path=db)
    with pytest.raises(ValueError, match="side"):
        add_transaction("hoa", pid, symbol="FPT", side="HOLD", quantity=1, price=10, db_path=db)
    with pytest.raises(ValueError, match="insufficient cash"):
        add_transaction(
            "hoa", pid, symbol="FPT", side="BUY", quantity=10, price=20_000, db_path=db
        )
    with pytest.raises(ValueError, match="insufficient quantity"):
        add_transaction(
            "hoa", pid, symbol="FPT", side="SELL", quantity=1, price=10, db_path=db
        )
    with pytest.raises(LookupError):
        add_transaction("other", pid, symbol="FPT", side="BUY", quantity=1, price=10, db_path=db)


def test_delete_transaction_reverses_cash(db: Path):
    p = create_portfolio("hoa", "Main", cash_balance=1_000_000, db_path=db)
    pid = p["id"]
    buy = add_transaction(
        "hoa", pid, symbol="HPG", side="BUY", quantity=10, price=20_000, fee=100, db_path=db
    )
    mid = list_portfolios("hoa", db_path=db)[0]["cash_balance"]
    assert mid == pytest.approx(1_000_000 - 200_000 - 100)
    assert delete_transaction("hoa", pid, buy["id"], db_path=db) is True
    assert list_portfolios("hoa", db_path=db)[0]["cash_balance"] == pytest.approx(1_000_000)
    assert position_qty(pid, "HPG", db_path=db) == 0
    assert list_transactions("hoa", pid, db_path=db) == []


def test_delete_portfolio_cascades_transactions(db: Path):
    p = create_portfolio("hoa", "X", cash_balance=500_000, db_path=db)
    add_transaction(
        "hoa", p["id"], symbol="SSI", side="BUY", quantity=10, price=10_000, db_path=db
    )
    assert delete_portfolio("hoa", p["id"], db_path=db) is True
    assert list_transactions("hoa", p["id"], db_path=db) is None


def test_api_portfolios_requires_auth(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_pf.db"
    import backend.desk_portfolio_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_portfolio_store(path)
    client = TestClient(app)
    assert client.get("/api/portfolios").status_code == 401
    assert client.post("/api/portfolios", json={"name": "A"}).status_code == 401


def test_api_portfolios_crud_and_transactions(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_pf.db"
    import backend.desk_portfolio_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_portfolio_store(path)
    client = TestClient(app)
    headers = {
        "X-Authentik-Username": "hoa",
        "X-Authentik-Groups": "members",
    }

    created = client.post(
        "/api/portfolios",
        headers=headers,
        json={
            "name": "Core",
            "description": "demo",
            "cash_balance": 2_000_000,
            "is_default": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["ok"] is True
    pid = body["item"]["id"]
    assert body["item"]["cash_balance"] == 2_000_000

    listed = client.get("/api/portfolios", headers=headers).json()
    assert any(i["id"] == pid for i in listed["items"])

    bad = client.post(
        f"/api/portfolios/{pid}/transactions",
        headers=headers,
        json={"symbol": "FPT", "side": "BUY", "quantity": 0, "price": 10},
    )
    assert bad.status_code == 422

    tx = client.post(
        f"/api/portfolios/{pid}/transactions",
        headers=headers,
        json={
            "symbol": "fpt",
            "side": "buy",
            "quantity": 20,
            "price": 50_000,
            "fee": 0,
        },
    )
    assert tx.status_code == 201
    payload = tx.json()
    assert payload["item"]["symbol"] == "FPT"
    assert payload["cash_balance"] == pytest.approx(2_000_000 - 1_000_000)
    assert payload["positions"][0]["qty"] == 20

    txs = client.get(f"/api/portfolios/{pid}/transactions", headers=headers).json()
    assert txs["ok"] is True and len(txs["items"]) == 1

    # other user cannot see
    other = {"X-Authentik-Username": "bob", "X-Authentik-Groups": "members"}
    assert client.get(f"/api/portfolios/{pid}/transactions", headers=other).status_code == 404

    deleted = client.delete(f"/api/portfolios/{pid}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == pid
    assert client.delete(f"/api/portfolios/{pid}", headers=headers).status_code == 404
