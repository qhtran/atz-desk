"""Token bucket dùng chung cho mọi nguồn. burst + refill (max_rpm-burst)/phút => mọi cửa sổ 60s <= max_rpm."""
from __future__ import annotations

import threading
import time
from collections import deque

from ingestion.log import ERR_RATE_LIMIT, log


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
        self.recent: deque[float] = deque()  # thời điểm cấp token trong 60s gần nhất
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
                log("RATE", f"throttle source={source} wait={wait:.3f}s max_rpm={self.max_rpm}",
                    error_code=ERR_RATE_LIMIT, source=source, rpm=len(self.recent))
                self.sleep(wait)
                self._refill()
            elif self.tokens <= self.warn_at:
                log("RATE", f"near-limit source={source} tokens={self.tokens:.2f}/{self.capacity:.0f}",
                    source=source, rpm=len(self.recent))
            self.tokens -= 1
            self.granted += 1
            now = self.clock()
            self.recent.append(now)
            self._trim(now)

    def _trim(self, now: float) -> None:
        while self.recent and now - self.recent[0] >= 60:
            self.recent.popleft()

    def current_rpm(self) -> int:
        with self._lock:
            self._trim(self.clock())
            return len(self.recent)
