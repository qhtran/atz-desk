"""Sổ vốn + risk per-user trên SQLite (ADR 0005)."""

from __future__ import annotations

import sqlite3

from datasource.capital_ledger import CapitalLedger
from datasource.user_trading import (
    FilterDefaults,
    filter_defaults_param_overlay,
    load_filter_defaults,
    load_pinned_symbols,
    load_user_trading,
    persist_capital_and_risk,
    persist_workspace,
    seed_filter_parameters,
    toggle_pinned_symbol,
)
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


def test_pin_toggle_persists(db: sqlite3.Connection) -> None:
    assert toggle_pinned_symbol("alice", "fpt", conn=db) == ["FPT"]
    assert toggle_pinned_symbol("alice", "vic", conn=db) == ["FPT", "VIC"]
    assert toggle_pinned_symbol("alice", "FPT", conn=db) == ["VIC"]
    assert load_pinned_symbols("alice", conn=db) == ["VIC"]
    assert load_pinned_symbols("bob", conn=db) == []


def test_filter_defaults_and_workspace_persist(db: sqlite3.Connection) -> None:
    defaults = load_filter_defaults("carol", conn=db)
    assert defaults.min_roe_pct == 12.0
    assert defaults.min_volume == 100_000.0

    prefs = FilterDefaults(
        min_roe_pct=15.0,
        min_volume=200_000.0,
        min_rs=5.0,
        top_n=10,
        rsi_oversold=25,
        rsi_overbought=75,
        macd_fast=10,
        macd_slow=20,
        macd_signal=7,
    )
    persist_workspace(
        "carol",
        CapitalLedger(80_000_000, 0, 0),
        5,
        prefs,
        ["fpt", "vic"],
        conn=db,
    )
    state = load_user_trading("carol", conn=db, migrate_csv=False)
    assert state.ledger.total == 80_000_000
    assert state.risk_tolerance_pct == 5
    loaded = load_filter_defaults("carol", conn=db)
    assert loaded.min_roe_pct == 15.0
    assert loaded.min_volume == 200_000.0
    assert loaded.min_rs == 5.0
    assert loaded.top_n == 10
    assert loaded.rsi_oversold == 25
    assert loaded.macd_fast == 10
    assert load_pinned_symbols("carol", conn=db) == ["FPT", "VIC"]
    profile = get_trading_profile(db, state.user_id)
    assert profile["filter_defaults"]["min_klgd"] == 200_000.0


def test_filter_defaults_param_overlay_maps_rsi_macd() -> None:
    prefs = FilterDefaults(
        min_roe_pct=12.0,
        min_volume=100_000.0,
        min_rs=-999.0,
        top_n=20,
        rsi_oversold=28,
        rsi_overbought=72,
        macd_fast=8,
        macd_slow=21,
        macd_signal=6,
    )
    overlay = filter_defaults_param_overlay(prefs)
    assert overlay["oversold"] == 28.0
    assert overlay["overbought"] == 72.0
    assert overlay["fast"] == 8
    assert overlay["slow"] == 21
    assert overlay["signal"] == 6


def test_seed_filter_parameters_saved_wins_and_skips_ma() -> None:
    overlay = {
        "oversold": 28.0,
        "overbought": 72.0,
        "fast": 8,
        "slow": 21,
        "signal": 6,
    }
    # RSI: seed oversold/overbought; saved oversold thắng
    rsi = seed_filter_parameters(
        ["mode", "length", "oversold", "overbought"],
        overlay,
        {"oversold": 30.0, "length": 14},
    )
    assert rsi["oversold"] == 30.0
    assert rsi["overbought"] == 72.0
    assert rsi["length"] == 14
    assert "fast" not in rsi

    # MACD: seed fast/slow/signal
    macd = seed_filter_parameters(
        ["mode", "fast", "slow", "signal"],
        overlay,
        {"fast": 12},
    )
    assert macd["fast"] == 12
    assert macd["slow"] == 21
    assert macd["signal"] == 6

    # MA: có fast/slow nhưng không signal → không lấy MACD prefs
    ma = seed_filter_parameters(["fast", "slow"], overlay, None)
    assert ma == {}
