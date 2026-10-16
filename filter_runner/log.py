"""Structured log (module FILTER) theo User_Manual_Troubleshooting_Realtime_Atz.md mục 2.

Mỗi dòng: `[DBG-YYYYMMDD-HHMM-FILTER-ACTION] [ERR-...] {json}`; giờ theo +07:00.
JSON luôn có: debug_label, error_code, module, symbol, user_id, latency_ms, message (+ batch_id, source, circuit_state khi liên quan).
Ghi ra stdout (docker logs) và ./logs/filter_runner.log (nếu FILTER_LOG_DIR ghi được).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger("filter_runner")
MODULE = "FILTER"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Bảng mã lỗi (User Manual mục 3 - Filter Runner + Chung)
ERR_TIMEOUT = "ERR-FILTER-001"
ERR_EXCEPTION = "ERR-FILTER-002"
ERR_DISABLED = "ERR-FILTER-003"
ERR_DEDUP = "ERR-FILTER-004"
ERR_SYS_REDIS = "ERR-SYS-001"
ERR_SYS_SQLITE = "ERR-SYS-002"
ERR_SYS_CONFIG = "ERR-SYS-003"


def setup(level: str = "INFO", log_dir: str | None = None) -> None:
    if LOGGER.handlers:
        return
    LOGGER.setLevel(level)
    fmt = logging.Formatter("%(message)s")
    out = logging.StreamHandler(sys.stdout)
    out.setFormatter(fmt)
    LOGGER.addHandler(out)
    log_dir = log_dir or os.environ.get("FILTER_LOG_DIR")
    if log_dir:
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(Path(log_dir) / "filter_runner.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8")
            fh.setFormatter(fmt)
            LOGGER.addHandler(fh)
        except OSError as error:
            log("HEALTH", f"file log disabled: {error}", logging.WARNING)


def label(action: str, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    return f"DBG-{now:%Y%m%d-%H%M}-{MODULE}-{action}"


def log(action: str, message: str, level: int = logging.INFO, *, error_code: str | None = None,
        symbol: str | None = None, user_id: str | None = None, latency_ms: int | None = None, **extra) -> None:
    now = datetime.now(TZ)
    debug_label = label(action, now)
    record = {"ts": now.isoformat(timespec="seconds"), "debug_label": debug_label, "error_code": error_code,
              "module": MODULE, "symbol": symbol, "user_id": user_id, "latency_ms": latency_ms,
              "message": message, **{k: v for k, v in extra.items() if v is not None}}
    if error_code and level < logging.WARNING:
        level = logging.WARNING
    prefix = f"[{debug_label}]" + (f" {error_code}" if error_code else "")
    LOGGER.log(level, "%s %s", prefix, json.dumps(record, ensure_ascii=False, default=str))
