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


@dataclass(frozen=True)
class FilterDefaults:
    """Mặc định bộ lọc / chỉ báo lưu trong trading_profile.filter_defaults."""

    min_roe_pct: float
    min_volume: float  # KLGD TB 20 phiên (min_klgd)
    min_rs: float
    top_n: int
    rsi_oversold: int
    rsi_overbought: int
    macd_fast: int
    macd_slow: int
    macd_signal: int


def _clamp_risk(value: int | float | None) -> int:
    from config import RISK_MAX, RISK_MIN

    try:
        number = int(value) if value is not None else int(RISK_DEFAULT)
    except (TypeError, ValueError):
        number = int(RISK_DEFAULT)
    return max(int(RISK_MIN), min(int(RISK_MAX), number))


def _as_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _as_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def default_filter_prefs() -> FilterDefaults:
    from config import (
        MACD_FAST,
        MACD_SIGNAL,
        MACD_SLOW,
        MIN_AVG_VOLUME,
        MIN_ROE,
        RS_FILTER_OFF,
        RSI_OVERBOUGHT,
        RSI_OVERSOLD,
        TOP_N,
        UNIVERSE,
    )

    return FilterDefaults(
        min_roe_pct=float(MIN_ROE * 100),
        min_volume=float(MIN_AVG_VOLUME),
        min_rs=float(RS_FILTER_OFF),
        top_n=max(5, min(int(TOP_N), len(UNIVERSE))),
        rsi_oversold=int(RSI_OVERSOLD),
        rsi_overbought=int(RSI_OVERBOUGHT),
        macd_fast=int(MACD_FAST),
        macd_slow=int(MACD_SLOW),
        macd_signal=int(MACD_SIGNAL),
    )


def _normalize_filter_defaults(raw: dict | None) -> FilterDefaults:
    from config import RS_FILTER_OFF, UNIVERSE

    base = default_filter_prefs()
    data = raw if isinstance(raw, dict) else {}
    # Alias min_klgd → min_volume (tên cũ trong handoff)
    volume = data.get("min_volume", data.get("min_klgd", base.min_volume))
    roe = data.get("min_roe_pct", data.get("min_roe", base.min_roe_pct))
    if "min_roe" in data and "min_roe_pct" not in data:
        # min_roe có thể là tỷ lệ 0–1 hoặc % — nếu ≤ 1 coi là tỷ lệ
        try:
            ratio = float(data["min_roe"])
            roe = ratio * 100 if 0 < ratio <= 1 else ratio
        except (TypeError, ValueError):
            roe = base.min_roe_pct
    rsi_lo = _as_int(data.get("rsi_oversold", base.rsi_oversold), base.rsi_oversold)
    rsi_hi = _as_int(data.get("rsi_overbought", base.rsi_overbought), base.rsi_overbought)
    if rsi_lo > rsi_hi:
        rsi_lo, rsi_hi = rsi_hi, rsi_lo
    return FilterDefaults(
        min_roe_pct=max(0.0, min(100.0, _as_float(roe, base.min_roe_pct))),
        min_volume=max(0.0, _as_float(volume, base.min_volume)),
        min_rs=max(float(RS_FILTER_OFF), min(200.0, _as_float(data.get("min_rs", base.min_rs), base.min_rs))),
        top_n=max(5, min(len(UNIVERSE), _as_int(data.get("top_n", base.top_n), base.top_n))),
        rsi_oversold=max(0, min(100, rsi_lo)),
        rsi_overbought=max(0, min(100, rsi_hi)),
        macd_fast=max(2, _as_int(data.get("macd_fast", base.macd_fast), base.macd_fast)),
        macd_slow=max(3, _as_int(data.get("macd_slow", base.macd_slow), base.macd_slow)),
        macd_signal=max(2, _as_int(data.get("macd_signal", base.macd_signal), base.macd_signal)),
    )


def filter_defaults_to_dict(prefs: FilterDefaults) -> dict:
    return {
        "min_roe_pct": float(prefs.min_roe_pct),
        "min_volume": float(prefs.min_volume),
        "min_klgd": float(prefs.min_volume),
        "min_rs": float(prefs.min_rs),
        "top_n": int(prefs.top_n),
        "rsi_oversold": int(prefs.rsi_oversold),
        "rsi_overbought": int(prefs.rsi_overbought),
        "macd_fast": int(prefs.macd_fast),
        "macd_slow": int(prefs.macd_slow),
        "macd_signal": int(prefs.macd_signal),
    }


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
        if "pinned_symbols" not in profile:
            profile["pinned_symbols"] = []
        set_trading_profile(db, user_id, profile)
        return user_id
    finally:
        if own:
            db.close()


def _normalize_pins(symbols: list | None, *, max_pins: int = 40) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in symbols or []:
        code = str(raw or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
        if len(out) >= max_pins:
            break
    return out


def load_pinned_symbols(username: str, *, conn=None) -> list[str]:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        profile = get_trading_profile(db, user_id)
        return _normalize_pins(profile.get("pinned_symbols"))
    finally:
        if own:
            db.close()


def save_pinned_symbols(username: str, symbols: list[str], *, conn=None) -> list[str]:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        profile = get_trading_profile(db, user_id)
        pins = _normalize_pins(symbols)
        profile["pinned_symbols"] = pins
        set_trading_profile(db, user_id, profile)
        return pins
    finally:
        if own:
            db.close()


def toggle_pinned_symbol(username: str, symbol: str, *, conn=None) -> list[str]:
    """Thêm mã nếu chưa ghim; bỏ nếu đã ghim. Trả danh sách mới."""
    code = str(symbol or "").strip().upper()
    pins = load_pinned_symbols(username, conn=conn)
    if not code:
        return pins
    if code in pins:
        pins = [p for p in pins if p != code]
    else:
        pins = _normalize_pins([*pins, code])
    return save_pinned_symbols(username, pins, conn=conn)


def load_filter_defaults(username: str, *, conn=None) -> FilterDefaults:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        profile = get_trading_profile(db, user_id)
        return _normalize_filter_defaults(profile.get("filter_defaults"))
    finally:
        if own:
            db.close()


def persist_filter_defaults(username: str, prefs: FilterDefaults, *, conn=None) -> FilterDefaults:
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        profile = get_trading_profile(db, user_id)
        clean = _normalize_filter_defaults(filter_defaults_to_dict(prefs))
        profile["filter_defaults"] = filter_defaults_to_dict(clean)
        if "custom_filters" not in profile:
            profile["custom_filters"] = {}
        set_trading_profile(db, user_id, profile)
        return clean
    finally:
        if own:
            db.close()


def persist_workspace(
    username: str,
    ledger: CapitalLedger,
    risk_pct: int,
    prefs: FilterDefaults,
    pins: list[str] | None = None,
    *,
    conn=None,
) -> FilterDefaults:
    """Lưu một lần: sổ vốn + risk + filter defaults + (tuỳ chọn) pin."""
    own = conn is None
    db = conn or open_signals()
    try:
        user_id = ensure_user(db, username)
        save_capital_ledger(db, user_id, ledger.initial, ledger.additional, ledger.withdrawn)
        profile = get_trading_profile(db, user_id)
        profile["risk_tolerance_pct"] = _clamp_risk(risk_pct)
        clean = _normalize_filter_defaults(filter_defaults_to_dict(prefs))
        profile["filter_defaults"] = filter_defaults_to_dict(clean)
        if pins is not None:
            profile["pinned_symbols"] = _normalize_pins(pins)
        elif "pinned_symbols" not in profile:
            profile["pinned_symbols"] = []
        if "custom_filters" not in profile:
            profile["custom_filters"] = {}
        set_trading_profile(db, user_id, profile)
        return clean
    finally:
        if own:
            db.close()
