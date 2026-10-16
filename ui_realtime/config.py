"""Đọc config/ui_realtime.yaml + env UI_*."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "ui_realtime.yaml"


def load(path=None) -> dict:
    path = Path(path or os.environ.get("UI_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if os.environ.get("UI_REDIS_URL"):
        doc["redis"]["url"] = os.environ["UI_REDIS_URL"]
    if os.environ.get("UI_SQLITE_PATH"):
        doc["sqlite"]["path"] = os.environ["UI_SQLITE_PATH"]
    for k in ("trading_sessions", "refresh_seconds_trading", "refresh_seconds_off", "cache_ttl_seconds", "health"):
        if k not in doc["ui_realtime"]:
            raise KeyError(f"thiếu ui_realtime.{k}")
    return doc
