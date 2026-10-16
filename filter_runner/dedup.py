"""Signal Deduplicator: SET NX EX trong Redis, cửa sổ 600s."""
from __future__ import annotations

import logging

from filter_runner.log import ERR_DEDUP, log


class Deduplicator:
    def __init__(self, redis_client, window: int, key_fmt: str, fail_open: bool):
        self.r, self.window, self.key_fmt, self.fail_open = redis_client, window, key_fmt, fail_open

    def first_seen(self, user_id: str, symbol: str, filter_name: str, direction: str) -> bool:
        key = self.key_fmt.format(user_id=user_id, symbol=symbol, filter_name=filter_name, direction=direction)
        try:
            fresh = bool(self.r.set(key, "1", nx=True, ex=self.window))
        except Exception as error:  # noqa: BLE001
            log("DEDUP", f"dedup check failed: {type(error).__name__}: {error} -> {'publish' if self.fail_open else 'drop'}",
                logging.ERROR, error_code=ERR_DEDUP, symbol=symbol, user_id=user_id, filter_name=filter_name)
            return self.fail_open
        if not fresh:
            log("DEDUP", f"duplicate suppressed within {self.window}s", symbol=symbol, user_id=user_id,
                filter_name=filter_name, direction=direction)
        return fresh
