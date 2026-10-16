"""Đọc config/position_monitor.yaml + env POS_*."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "position_monitor.yaml"
ENV = {
    "REDIS_URL": (("redis", "url"), str),
    "POS_SQLITE_PATH": (("sqlite", "path"), str),
    "POS_CONSUMER_NAME": (("position_monitor", "consumer", "consumer_name"), str),
    "POS_MAX_QUOTE_AGE_SECONDS": (("position_monitor", "stale", "max_quote_age_seconds"), float),
}
SECTIONS = ("consumer", "stale", "volatility", "alert", "live", "health")


def load(path=None) -> dict:
    path = Path(path or os.environ.get("POS_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, (keys, cast) in ENV.items():
        raw = os.environ.get(name)
        if raw in (None, ""):
            continue
        node = doc
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = cast(raw)
    for s in SECTIONS:
        if s not in doc["position_monitor"]:
            raise KeyError(f"thiếu position_monitor.{s}")
    return doc
