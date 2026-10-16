"""Health command: `python -m ingestion.health` -> exit 0 nếu Redis OK và heartbeat còn mới."""
from __future__ import annotations

import json
import sys
import time

from ingestion import config
from ingestion.log import log, setup
from ingestion.store import RedisStore


def check(settings=None, store=None) -> tuple[bool, dict]:
    settings = settings or config.load()
    store = store or RedisStore(settings)
    try:
        store.r.ping()
    except Exception as error:  # noqa: BLE001
        return False, {"redis": f"down: {error}"}
    beat = store.read_health()
    if not beat:
        return False, {"redis": "ok", "heartbeat": "missing"}
    age = time.time() - float(beat.get("epoch", 0))
    ok = age <= settings.health_max_age_seconds
    return ok, {"redis": "ok", "heartbeat_age_s": round(age, 1), **beat}


def main() -> int:
    setup()
    ok, info = check()
    log("HEALTH", ("OK " if ok else "FAIL ") + json.dumps(info, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
