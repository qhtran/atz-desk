"""Vòng lặp chính: `python -m filter_runner`."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

from filter_runner import config
from filter_runner.log import ERR_SYS_CONFIG, ERR_SYS_REDIS, log, setup

RUNNING = True
HEALTH_EVERY = float(os.environ.get("FILTER_HEALTH_WRITE_SECONDS", "15"))
HEALTH_LOG_EVERY = float(os.environ.get("FILTER_HEALTH_LOG_SECONDS", "300"))


def _stop(*_):
    global RUNNING
    RUNNING = False


def main() -> None:
    setup(os.environ.get("FILTER_LOG_LEVEL", "INFO"))
    try:
        cfg = config.load()
    except Exception as error:  # noqa: BLE001
        log("HEALTH", f"config load failed: {type(error).__name__}: {error}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        sys.exit(1)
    from filter_runner.runner import FilterRunner
    runner = FilterRunner(cfg)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log("HEALTH", f"start filters={runner.registry.names()} stream={runner.consumer.stream} group={runner.consumer.group}")
    last_beat = last_log = 0.0
    while RUNNING:
        try:
            runner.step()
        except Exception as error:  # noqa: BLE001 - vòng lặp không được chết
            log("CONSUME", f"step error: {type(error).__name__}: {error}", logging.ERROR)
            time.sleep(2)
        now = time.monotonic()
        if now - last_beat >= HEALTH_EVERY:
            try:
                beat = runner.write_health()
                last_beat = now
                if now - last_log >= HEALTH_LOG_EVERY:
                    last_log = now
                    log("HEALTH", "filter_runner_health", signals_per_minute=beat["signals_per_minute"],
                        disabled_filters=beat["disabled_filters"], lag=beat["lag"], events=beat["events"],
                        signals=beat["signals"])
            except Exception as error:  # noqa: BLE001
                log("HEALTH", f"heartbeat write failed: {error}", logging.ERROR, error_code=ERR_SYS_REDIS)
    log("HEALTH", "stopped")


if __name__ == "__main__":
    main()
