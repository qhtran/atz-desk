"""Structured logging for priceboard (module tag PB).

Line format: `[DBG-YYYYMMDD-HHMM-PB-ACTION] ERR-PB-NNN {json}`
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.observability.origin import capture_origin, stack_tail

MODULE = "PB"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

COMPONENT_LOGGERS: dict[str, str] = {
    "api": "atz.priceboard.api",
    "redis": "atz.priceboard.redis_listener",
    "ws": "atz.priceboard.ws",
    "worker": "atz.priceboard.ssi_worker",
    "ssi_live": "atz.priceboard.ssi_live",
    "ssi_rest": "atz.priceboard.ssi_rest",
}

_CONFIGURED: set[str] = set()


def setup(component: str, *, level: str | None = None, log_dir: str | None = None) -> logging.Logger:
    """Configure stdout (+ optional file) for one priceboard component."""
    name = COMPONENT_LOGGERS.get(component)
    if not name:
        raise ValueError(f"unknown priceboard component: {component}")
    logger = logging.getLogger(name)
    if component in _CONFIGURED:
        return logger
    lvl = getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logger.setLevel(lvl)
    logger.propagate = False
    fmt = logging.Formatter("%(message)s")
    out = logging.StreamHandler(sys.stdout)
    out.setFormatter(fmt)
    logger.addHandler(out)
    log_dir = log_dir or os.environ.get("PRICEBOARD_LOG_DIR")
    if log_dir:
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                Path(log_dir) / f"{component}.log",
                maxBytes=10_000_000,
                backupCount=5,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except OSError as err:
            log(component, "HEALTH", f"file log disabled: {err}", logging.WARNING)
    _CONFIGURED.add(component)
    return logger


def get_logger(component: str) -> logging.Logger:
    name = COMPONENT_LOGGERS[component]
    return logging.getLogger(name)


def label(action: str, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    safe = action.replace(" ", "-").upper()
    return f"DBG-{now:%Y%m%d-%H%M}-{MODULE}-{safe}"


def log(
    component: str,
    action: str,
    message: str,
    level: int = logging.INFO,
    *,
    error_code: str | None = None,
    exc: BaseException | None = None,
    **extra: Any,
) -> None:
    logger = get_logger(component)
    now = datetime.now(TZ)
    debug_label = label(action, now)
    record: dict[str, Any] = {
        "ts": now.isoformat(timespec="seconds"),
        "debug_label": debug_label,
        "error_code": error_code,
        "module": MODULE,
        "message": message,
        **{k: v for k, v in extra.items() if v is not None},
    }
    if error_code is not None or level >= logging.ERROR:
        record["origin"] = capture_origin(exc=exc, depth=1)
    if exc is not None:
        record["exc_type"] = type(exc).__name__
        record["exc_message"] = str(exc)[:500]
        if os.getenv("LOG_TRACE_STACK", "").strip() in ("1", "true", "yes"):
            record["stack_tail"] = stack_tail(exc, limit=3)
    if error_code and level < logging.WARNING:
        level = logging.WARNING
    prefix = f"[{debug_label}]" + (f" {error_code}" if error_code else "")
    logger.log(level, "%s %s", prefix, json.dumps(record, ensure_ascii=False, default=str))
