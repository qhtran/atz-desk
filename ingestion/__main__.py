"""Vòng lặp chính: `python -m ingestion`."""
from __future__ import annotations

import os
import signal
import time

from ingestion import config
from ingestion.log import log, setup
from ingestion.orchestrator import Orchestrator
from ingestion.store import RedisStore

RUNNING = True


def _stop(*_):
    global RUNNING
    RUNNING = False


def main() -> None:
    setup(os.environ.get("INGEST_LOG_LEVEL", "INFO"))
    settings = config.load()
    store = RedisStore(settings)
    orch = Orchestrator(settings, store)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log("HEALTH", f"start primary={settings.primary_source} fallback={settings.fallback_source} "
                  f"symbols={len(settings.symbols)} batch={settings.batch_size} max_rpm={settings.safety_max_rpm}")
    while RUNNING:
        try:
            orch.run_cycle()
        except Exception as error:  # noqa: BLE001 - vòng lặp không được chết
            log("HEALTH", f"cycle error: {type(error).__name__}: {error}")
        try:
            store.write_health(orch.health())
        except Exception as error:  # noqa: BLE001
            log("HEALTH", f"heartbeat write failed: {error}")
        wait = orch.interval()
        end = time.monotonic() + wait
        while RUNNING and time.monotonic() < end:
            time.sleep(0.5)
    log("HEALTH", "stopped")


if __name__ == "__main__":
    main()
