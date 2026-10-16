"""Token bucket dùng chung cho mọi nguồn. burst + refill (max_rpm-burst)/phút => mọi cửa sổ 60s <= max_rpm."""
from __future__ import annotations

import threading
import time

from ingestion.log import log


class TokenBucket:
    def __init__(self, max_rpm: int, burst: int, warn_ratio: float = 0.2,
                 clock=time.monotonic, sleep=time.sleep):
        if not 0 < burst < max_rpm:
            raise ValueError("burst phải nằm trong (0, max_rpm)")
        self.capacity = float(burst)
        self.rate = (max_rpm - burst) / 60.0  # token / giây
        self.max_rpm = max_rpm
        self.warn_at = max(1.0, burst * warn_ratio)
        self.clock, self.sleep = clock, sleep
        self.tokens = float(burst)
        self.updated = clock()
        self.granted = 0
        self.throttled = 0
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
        self.updated = now

    def acquire(self, source: str = "-") -> None:
        with self._lock:
            self._refill()
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                self.throttled += 1
                log("RATE", f"throttle source={source} wait={wait:.3f}s max_rpm={self.max_rpm}")
                self.sleep(wait)
                self._refill()
            elif self.tokens <= self.warn_at:
                log("RATE", f"near-limit source={source} tokens={self.tokens:.2f}/{self.capacity:.0f}")
            self.tokens -= 1
            self.granted += 1
