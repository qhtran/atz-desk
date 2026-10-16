"""Đọc config/filter_runner.yaml + env. Trả dict lồng (đơn giản, tường minh)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "filter_runner.yaml"
ENV = {  # env -> (đường dẫn trong yaml, kiểu)
    "REDIS_URL": (("redis", "url"), str),
    "FILTER_SQLITE_PATH": (("sqlite", "path"), str),
    "FILTER_CONSUMER_NAME": (("filter_runner", "consumer", "consumer_name"), str),
    "FILTER_TIMEOUT_SECONDS": (("filter_runner", "evaluator", "timeout_seconds"), float),
    "FILTER_DEDUP_WINDOW_SECONDS": (("filter_runner", "dedup", "window_seconds"), int),
    "FILTER_REMOTE_FETCH": (("filter_runner", "history", "remote_fetch"), lambda v: v.lower() in ("1", "true", "yes")),
}


def load(path=None) -> dict:
    path = Path(path or os.environ.get("FILTER_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, (keys, cast) in ENV.items():
        raw = os.environ.get(name)
        if raw in (None, ""):
            continue
        node = doc
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = cast(raw)
    fr = doc["filter_runner"]
    for section in ("consumer", "evaluator", "filter_circuit", "dedup", "publisher", "backpressure",
                    "history", "resolver", "health"):
        if section not in fr:
            raise KeyError(f"thiếu filter_runner.{section}")
    return doc
