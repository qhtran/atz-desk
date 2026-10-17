"""Sổ vốn + profile trade per-user trên SQLite (ADR 0004 / 0005).

CSV capital_ledger.csv chỉ dùng để migrate một lần khi user chưa có dòng SQLite.
Không ghi Redis; không đụng Authentik.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import RISK_DEFAULT
from datasource.capital_ledger import CapitalLedger, default_ledger, load_ledger
from storage.db import open_signals
from storage.repository import (
    ensure_user,
    get_capital_ledger,
    get_trading_profile,
    save_capital_ledger,
    set_trading_profile,
)


@dataclass(frozen=True)
class UserTradingState:
    user_id: int
    username: str
    ledger: CapitalLedger
    risk_tolerance_pct: int
    profile: dict


def _clamp_risk(value: int | float | None) -> int:
    from config import RISK_MAX, RISK_MIN

    try:
        number = int(value) if value is not None else int(RISK_DEFAULT)
    except (TypeError, ValueError):
        number = int(RISK_DEFAULT)
    return max(int(RISK_MIN), min(int(RISK_MAX), number))


def _ledger_from_row(row: dict[str, float] | None) -> CapitalLedger | None:
    if row is None:
        return None
    initial = max(0.0, float(row["initial"]))
    additional = max(0.0, float(row["additional"]))
    withdrawn = max(0.0, float(row["withdrawn"]))
    if initial <= 0 and additional <= 0:
        return None
    return CapitalLedger(initial=initial, additional=additional, withdrawn=withdrawn)


def load_user_trading(username: str, *, conn=None, migrate_csv: bool = True) -> UserTradingState:
    """Đảm bảo user tồn tại; đọc sổ vốn + risk từ SQLite (fallback default / CSV một lần)."""
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        row = get_capital_ledger(db, user_id)
        ledger = _ledger_from_row(row)
        if ledger is None and migrate_csv:
            legacy = load_ledger()
            if legacy.total > 0 and (legacy.initial > 0 or legacy.additional > 0):
                save_capital_ledger(db, user_id, legacy.initial, legacy.additional, legacy.withdrawn)
                ledger = legacy
        if ledger is None:
            ledger = default_ledger()
        profile = get_trading_profile(db, user_id)
        risk = _clamp_risk(profile.get("risk_tolerance_pct", RISK_DEFAULT))
        return UserTradingState(
            user_id=user_id,
            username=username.strip() or "local",
            ledger=ledger,
            risk_tolerance_pct=risk,
            profile=profile,
        )
    finally:
        if own:
            db.close()


def persist_capital(username: str, ledger: CapitalLedger, *, conn=None) -> int:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        save_capital_ledger(db, user_id, ledger.initial, ledger.additional, ledger.withdrawn)
        return user_id
    finally:
        if own:
            db.close()


def persist_risk(username: str, risk_pct: int, *, conn=None) -> int:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        profile = get_trading_profile(db, user_id)
        profile["risk_tolerance_pct"] = _clamp_risk(risk_pct)
        set_trading_profile(db, user_id, profile)
        return user_id
    finally:
        if own:
            db.close()


def persist_capital_and_risk(
    username: str,
    ledger: CapitalLedger,
    risk_pct: int,
    *,
    conn=None,
) -> int:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        save_capital_ledger(db, user_id, ledger.initial, ledger.additional, ledger.withdrawn)
        profile = get_trading_profile(db, user_id)
        profile["risk_tolerance_pct"] = _clamp_risk(risk_pct)
        if "custom_filters" not in profile:
            profile["custom_filters"] = {}
        set_trading_profile(db, user_id, profile)
        return user_id
    finally:
        if own:
            db.close()
