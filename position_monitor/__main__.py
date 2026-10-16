"""Vòng lặp chính: `python -m position_monitor`."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

import redis

from position_monitor import config
from position_monitor.log import ERR_SYS_CONFIG, ERR_SYS_REDIS, log, setup

RUNNING = True
HEALTH_EVERY = float(os.environ.get("POS_HEALTH_WRITE_SECONDS", "15"))
HEALTH_LOG_EVERY = float(os.environ.get("POS_HEALTH_LOG_SECONDS", "300"))


def _stop(*_):
    global RUNNING
    RUNNING = False


def main() -> None:
    setup(os.environ.get("POS_LOG_LEVEL", "INFO"))
    try:
        cfg = config.load()
    except Exception as error:  # noqa: BLE001
        log("HEALTH", f"config load failed: {type(error).__name__}: {error}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        sys.exit(1)
    from position_monitor.monitor import Monitor
    runner = Monitor(cfg)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    runner.reload(force=True)
    log("HEALTH", f"start open_positions={len(runner.positions)} stream={runner.stream} group={runner.group}")
    last_beat = last_log = 0.0
    while RUNNING:
        try:
            runner.step()
        except Exception as error:  # noqa: BLE001 - vòng lặp không được chết
            code = ERR_SYS_REDIS if isinstance(error, (redis.exceptions.RedisError, TimeoutError)) else None
            log("CONSUME", f"step error: {type(error).__name__}: {error}", logging.ERROR, error_code=code)
            time.sleep(2)
        now = time.monotonic()
        if now - last_beat >= HEALTH_EVERY:
            try:
                beat = runner.write_health()
                last_beat = now
                if now - last_log >= HEALTH_LOG_EVERY:
                    last_log = now
                    log("HEALTH", "position_monitor_health", open_positions=beat["open_positions"],
                        stale_positions=beat["stale_positions"], events=beat["events"], alerts=beat["alerts"],
                        pnl_errors=beat["pnl_errors"])
            except Exception as error:  # noqa: BLE001
                log("HEALTH", f"heartbeat write failed: {error}", logging.ERROR, error_code=ERR_SYS_REDIS)
    log("HEALTH", "stopped")


if __name__ == "__main__":
    main()
