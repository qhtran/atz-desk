"""Structured log theo docs/troubleshooting.md mục 2.

Mỗi dòng: `[DBG-YYYYMMDD-HHMM-INGEST-ACTION] [ERR-...] {json}`; giờ theo +07:00.
JSON luôn có: debug_label, error_code, module, symbol, user_id, latency_ms, message (+ batch_id, source, circuit_state khi liên quan).
Ghi ra stdout (docker logs) và ./logs/ingestion.log (nếu INGEST_LOG_DIR ghi được).
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

LOGGER = logging.getLogger("ingestion")
MODULE = "INGEST"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Bảng mã lỗi (mục 3 tài liệu)
ERR_RATE_LIMIT = "ERR-INGEST-001"
ERR_KBS_OPEN = "ERR-INGEST-002"
ERR_VCI_OPEN = "ERR-INGEST-003"
ERR_BOTH_DOWN = "ERR-INGEST-004"
ERR_NORMALIZE = "ERR-INGEST-005"
ERR_REDIS_WRITE = "ERR-INGEST-006"
ERR_TIMEOUT = "ERR-INGEST-007"
ERR_SYS_REDIS = "ERR-SYS-001"
ERR_SYS_CONFIG = "ERR-SYS-003"
CIRCUIT_OPEN_CODES = {"KBS": ERR_KBS_OPEN, "VCI": ERR_VCI_OPEN}


def setup(level: str = "INFO", log_dir: str | None = None) -> None:
    if LOGGER.handlers:
        return
    LOGGER.setLevel(level)
    fmt = logging.Formatter("%(message)s")
    out = logging.StreamHandler(sys.stdout)
    out.setFormatter(fmt)
    LOGGER.addHandler(out)
    log_dir = log_dir or os.environ.get("INGEST_LOG_DIR")
    if log_dir:
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(Path(log_dir) / "ingestion.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8")
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
