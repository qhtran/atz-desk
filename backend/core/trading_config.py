"""Load config/trading_station.yaml (+ Phase 3A risk / scoring scaffolding)."""

from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(os.getenv("TRADING_CONFIG", "config/trading_station.yaml"))

_DEFAULTS: dict[str, Any] = {
    "brokerage_fee_rate": 0.0015,
    "sell_tax_rate": 0.001,
    "max_tranche": 5,
    "default_user": "default_user",
    "redis_hash": "priceboard:quotes",
    "quote_field": "last",
    "position_sizing": {
        "default_equity_pct": None,
        "max_positions": None,
        "min_lot": 100,
        "tranche_weights": [],
    },
    "risk_tolerance": {
        "default_profile": "default",
        "user_profiles": {},
        "profiles": {
            "default": {
                "stop_loss_pct": None,
                "take_profit_pct": None,
                "max_portfolio_risk_pct": None,
            }
        },
    },
    "scoring_thresholds": {
        "weights": {"trend": 0.40, "flow": 0.30, "short_term": 0.30},
        "buy_min_total": 65,
        "sell_max_total": 35,
        "trend": {"ma_fast": 10, "ma_slow": 50, "cross_window": 2},
        "flow": {
            "foreign_days": 5,
            "foreign_min_net_vol": 0,
            "volume_avg": 20,
            "volume_spike": 2.0,
        },
        "short_term": {
            "rsi_length": 14,
            "rsi_buy_zone": [30, 45],
            "rsi_sell_above": 70,
            "bb_length": 20,
            "bb_k": 2.0,
        },
        "profiles": {},
    },
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


@lru_cache
def load_trading_config(path: str | None = None) -> dict:
    cfg_path = Path(path) if path else DEFAULT_PATH
    if not cfg_path.is_file():
        return copy.deepcopy(_DEFAULTS)
    with cfg_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return copy.deepcopy(_DEFAULTS)
    return _deep_merge(_DEFAULTS, data)


def resolve_risk_profile_key(username: str | None, cfg: dict | None = None) -> str:
    """Map Authentik username → risk_tolerance profile key."""
    data = cfg or load_trading_config()
    risk = data.get("risk_tolerance") or {}
    default_key = str(risk.get("default_profile") or "default")
    users = risk.get("user_profiles") or {}
    if username and str(username) in users:
        return str(users[str(username)])
    profiles = risk.get("profiles") or {}
    if default_key in profiles:
        return default_key
    if "default" in profiles:
        return "default"
    return next(iter(profiles), "default")


def risk_meta_for_user(username: str | None, cfg: dict | None = None) -> dict[str, Any]:
    data = cfg or load_trading_config()
    risk = data.get("risk_tolerance") or {}
    profile_key = resolve_risk_profile_key(username, data)
    profiles = risk.get("profiles") or {}
    profile = copy.deepcopy(profiles.get(profile_key) or {})
    sizing = copy.deepcopy(data.get("position_sizing") or {})
    return {
        "username": username or "",
        "profile": profile_key,
        "stop_loss_pct": profile.get("stop_loss_pct"),
        "take_profit_pct": profile.get("take_profit_pct"),
        "max_portfolio_risk_pct": profile.get("max_portfolio_risk_pct"),
        "position_sizing": sizing,
        "note": profile.get("note") or "",
    }


def scoring_config_for_user(username: str | None, cfg: dict | None = None) -> dict[str, Any]:
    """scoring_thresholds + optional per-profile overlay."""
    data = cfg or load_trading_config()
    base = copy.deepcopy(data.get("scoring_thresholds") or {})
    profile_key = resolve_risk_profile_key(username, data)
    overlays = base.pop("profiles", {}) or {}
    overlay = overlays.get(profile_key) or {}
    if isinstance(overlay, dict) and overlay:
        base = _deep_merge(base, overlay)
    base["_profile"] = profile_key
    return base
