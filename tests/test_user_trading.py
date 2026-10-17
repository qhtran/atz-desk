"""Sổ vốn + risk per-user trên SQLite (ADR 0005)."""

from __future__ import annotations

import sqlite3

from datasource.capital_ledger import CapitalLedger
from datasource.user_trading import load_user_trading, persist_capital_and_risk
from storage.repository import ensure_user, get_capital_ledger, get_trading_profile


def test_two_users_isolated_ledgers(db: sqlite3.Connection) -> None:
    persist_capital_and_risk(
        "alice",
        CapitalLedger(100_000_000, 0, 0),
        2,
        conn=db,
    )
    persist_capital_and_risk(
        "bob",
        CapitalLedger(50_000_000, 10_000_000, 5_000_000),
        4,
        conn=db,
    )
    alice = load_user_trading("alice", conn=db, migrate_csv=False)
    bob = load_user_trading("bob", conn=db, migrate_csv=False)
    assert alice.ledger.total == 100_000_000
    assert bob.ledger.total == 55_000_000
    assert alice.risk_tolerance_pct == 2
    assert bob.risk_tolerance_pct == 4
    assert alice.user_id != bob.user_id


def test_profile_custom_filters_bucket(db: sqlite3.Connection) -> None:
    uid = persist_capital_and_risk("local", CapitalLedger(100_000_000, 0, 0), 3, conn=db)
    profile = get_trading_profile(db, uid)
    assert profile["risk_tolerance_pct"] == 3
    assert profile.get("custom_filters") == {}


def test_default_ledger_when_empty(db: sqlite3.Connection) -> None:
    ensure_user(db, "newbie")
    state = load_user_trading("newbie", conn=db, migrate_csv=False)
    assert state.ledger.total > 0
    assert get_capital_ledger(db, state.user_id) is None  # chưa persist
