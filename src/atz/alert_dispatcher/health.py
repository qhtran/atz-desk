"""Health command: `python -m alert_dispatcher.health` -> alert_health (tỷ lệ gửi thành công theo kênh, circuit) + redis ping."""
from __future__ import annotations

import json
import logging
import sys
import time

import redis

from alert_dispatcher import config
from alert_dispatcher.log import ERR_SYS_CONFIG, ERR_SYS_REDIS, log, setup


def check(cfg=None, r=None) -> tuple[bool, dict]:
    cfg = cfg or config.load()
    r = r or redis.Redis.from_url(cfg["redis"]["url"], decode_responses=True, socket_timeout=5)
    h = cfg["alert_dispatcher"]["health"]
    try:
        r.ping()
        raw = r.get(h["key"])
    except Exception as error:  # noqa: BLE001
        return False, {"redis": f"down: {error}", "error_code": ERR_SYS_REDIS}
    if not raw:
        return False, {"redis": "ok", "alert_health": "heartbeat missing"}
    beat = json.loads(raw)
    age = round(time.time() - float(beat.get("epoch", 0)), 1)
    return age <= h["max_age_seconds"], {"alert_health": {"heartbeat_age_s": age, **beat}}


def main() -> int:
    setup()
    try:
        cfg = config.load()
    except Exception as error:  # noqa: BLE001
        log("HEALTH", f"config load failed: {error}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        return 1
    ok, info = check(cfg)
    log("HEALTH", ("OK " if ok else "FAIL ") + json.dumps(info, ensure_ascii=False),
        logging.INFO if ok else logging.ERROR, error_code=info.get("error_code"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
