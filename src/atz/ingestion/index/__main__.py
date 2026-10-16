"""`python -m ingestion.index`: vòng lặp feed chỉ số (container atz-index). Không đụng quote vnstock 350 rpm."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

import redis

from ingestion.index.common import load, log
from ingestion.index.feed import IndexFeed
from ingestion.log import ERR_SYS_CONFIG, setup

RUNNING = True


def _stop(*_):
    global RUNNING
    RUNNING = False


def main() -> None:
    setup(os.environ.get("IDX_LOG_LEVEL", "INFO"))
    try:
        s = load()
    except Exception as err:  # noqa: BLE001
        log("HEALTH", f"config load failed: {err}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        sys.exit(1)
    r = redis.Redis.from_url(s.redis_url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3)
    feed = IndexFeed(s, r)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log("HEALTH", f"start providers={[(e['p'].name, e['p'].enabled) for e in feed.providers]} symbols={s.symbols}")
    try:
        feed.backfill()
    except Exception as err:  # noqa: BLE001
        log("BACKFILL", f"failed: {type(err).__name__}: {err}", logging.ERROR)
    while RUNNING:
        try:
            q = feed.cycle()
            if feed.cycles % 20 == 1:
                log("FETCH", f"cycle #{feed.cycles} quotes={len(q)}/{len(s.symbols)} "
                             + " ".join(f"{k}={v.value}({v.source[0]})" for k, v in q.items()))
        except Exception as err:  # noqa: BLE001 - vòng lặp không được chết
            log("HEALTH", f"cycle error: {type(err).__name__}: {err}", logging.ERROR)
        feed.write_health()
        end = time.monotonic() + feed.interval()
        while RUNNING and time.monotonic() < end:
            time.sleep(0.5)
    log("HEALTH", "stopped")


if __name__ == "__main__":
    main()
