"""Vòng lặp chính: `python -m ingestion`."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

from ingestion import config
from ingestion.log import ERR_SYS_CONFIG, ERR_SYS_REDIS, log, setup
from ingestion.orchestrator import Orchestrator
from ingestion.store import RedisStore

RUNNING = True
HEALTH_LOG_EVERY = int(os.environ.get("INGEST_HEALTH_LOG_EVERY", "30"))  # log health định kỳ mỗi N chu kỳ


def _stop(*_):
    global RUNNING
    RUNNING = False


def main() -> None:
    setup(os.environ.get("INGEST_LOG_LEVEL", "INFO"))
    try:
        settings = config.load()
    except Exception as error:  # noqa: BLE001
        log("HEALTH", f"config load failed: {type(error).__name__}: {error}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        sys.exit(1)
    store = RedisStore(settings)
    orch = Orchestrator(settings, store)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log("HEALTH", f"start primary={settings.primary_source} fallback={settings.fallback_source} "
                  f"symbols_mode={settings.symbols_mode} symbols={len(settings.symbols)} "
                  f"batch={settings.batch_size} max_rpm={settings.safety_max_rpm}")
    while RUNNING:
        try:
            orch.run_cycle()
        except Exception as error:  # noqa: BLE001 - vòng lặp không được chết
            log("HEALTH", f"cycle error: {type(error).__name__}: {error}", logging.ERROR)
        try:
            beat = orch.health()
            store.write_health(beat)
            if orch.metrics["cycles"] % HEALTH_LOG_EVERY == 1:
                log("HEALTH", "ingestion_health", circuit_state=beat["breakers"], current_rpm=beat["current_rpm"],
                    last_successful_fetch=beat["last_successful_fetch"], mode=beat["mode"],
                    redis_health=store.redis_health())
        except Exception as error:  # noqa: BLE001
            log("HEALTH", f"heartbeat write failed: {error}", logging.ERROR, error_code=ERR_SYS_REDIS)
        wait = orch.interval()
        end = time.monotonic() + wait
        while RUNNING and time.monotonic() < end:
            time.sleep(0.5)
    log("HEALTH", "stopped")


if __name__ == "__main__":
    main()
