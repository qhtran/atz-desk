"""Structured log cho UI: [DBG-YYYYMMDD-HHMM-UI-ACTION] {json}. Mọi dòng có debug_label."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger("ui_realtime")
MODULE = "UI"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ERR_SYS_REDIS = "ERR-SYS-001"
ERR_SYS_SQLITE = "ERR-SYS-002"
ERR_SYS_CONFIG = "ERR-SYS-003"
ERR_UI_INPUT = "ERR-UI-001"      # dữ liệu nhập vị thế không hợp lệ
ERR_UI_FORBIDDEN = "ERR-UI-002"  # thao tác vị thế không thuộc user đăng nhập
ERR_UI_SETTINGS = "ERR-UI-003"   # cài đặt thông báo không hợp lệ
ERR_UI_FALLBACK = "ERR-UI-004"   # bảng giá chạy chế độ dự phòng (Redis down / không có quote)
ERR_UI_INDEX = "ERR-UI-007"      # thẻ chỉ số không đọc được Redis (idx:quote / spark)

if not LOGGER.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(_h)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = True


def label(action: str, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    return f"DBG-{now:%Y%m%d-%H%M}-{MODULE}-{action}"


def log(action: str, message: str, level: int = logging.INFO, *, error_code: str | None = None,
        symbol: str | None = None, user_id=None, latency_ms: int | None = None, **extra) -> None:
    now = datetime.now(TZ)
    dl = label(action, now)
    rec = {"ts": now.isoformat(timespec="seconds"), "debug_label": dl, "error_code": error_code, "module": MODULE,
           "symbol": symbol, "user_id": None if user_id is None else str(user_id), "latency_ms": latency_ms,
           "message": message, **{k: v for k, v in extra.items() if v is not None}}
    if error_code and level < logging.WARNING:
        level = logging.WARNING
    LOGGER.log(level, "%s %s", f"[{dl}]" + (f" {error_code}" if error_code else ""),
               json.dumps(rec, ensure_ascii=False, default=str))
