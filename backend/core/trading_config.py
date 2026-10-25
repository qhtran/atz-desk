"""Load config/trading_station.yaml."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_PATH = Path(os.getenv("TRADING_CONFIG", "config/trading_station.yaml"))


@lru_cache
def load_trading_config(path: str | None = None) -> dict:
    cfg_path = Path(path) if path else DEFAULT_PATH
    if not cfg_path.is_file():
        return {
            "brokerage_fee_rate": 0.0015,
            "sell_tax_rate": 0.001,
            "max_tranche": 5,
            "default_user": "default_user",
            "redis_hash": "priceboard:quotes",
            "quote_field": "last",
        }
    with cfg_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data
