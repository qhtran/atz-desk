"""Health command: `python -m ingestion.health`.

In ra ingestion_health (circuit KBS/VCI, last successful fetch, rpm hiện tại) và redis_health (ping + memory).
Exit 0 khi Redis OK và heartbeat của service còn mới; ngược lại exit 1.
"""
from __future__ import annotations

import json
import logging
import sys
import time

from ingestion import config
from ingestion.log import ERR_SYS_CONFIG, ERR_SYS_REDIS, log, setup
from ingestion.store import RedisStore


def check(settings=None, store=None) -> tuple[bool, dict]:
    settings = settings or config.load()
    store = store or RedisStore(settings)
    try:
        redis_health = store.redis_health()
    except Exception as error:  # noqa: BLE001
        return False, {"redis_health": {"ping": f"down: {error}"}, "error_code": ERR_SYS_REDIS}
    beat = store.read_health()
    if not beat:
        return False, {"redis_health": redis_health, "ingestion_health": "heartbeat missing"}
    age = round(time.time() - float(beat.get("epoch", 0)), 1)
    ok = age <= settings.health_max_age_seconds
    return ok, {"ingestion_health": {"heartbeat_age_s": age, **beat}, "redis_health": redis_health}


def main() -> int:
    setup()
    try:
        settings = config.load()
    except Exception as error:  # noqa: BLE001
        log("HEALTH", f"config load failed: {error}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        return 1
    ok, info = check(settings)
    log("HEALTH", ("OK " if ok else "FAIL ") + json.dumps(info, ensure_ascii=False),
        logging.INFO if ok else logging.ERROR, error_code=info.get("error_code"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
