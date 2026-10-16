"""Đọc config/alert_dispatcher.yaml + env."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "alert_dispatcher.yaml"
SECTIONS = ("consumer", "channels", "routing", "circuit", "rate_limit", "quiet_hours", "dedup", "health")


def load(path=None) -> dict:
    path = Path(path or os.environ.get("ALERT_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if os.environ.get("REDIS_URL"):
        doc["redis"]["url"] = os.environ["REDIS_URL"]
    if os.environ.get("ALERT_SQLITE_PATH"):
        doc["sqlite"]["path"] = os.environ["ALERT_SQLITE_PATH"]
    ad = doc["alert_dispatcher"]
    for s in SECTIONS:
        if s not in ad:
            raise KeyError(f"thiếu alert_dispatcher.{s}")
    return doc
