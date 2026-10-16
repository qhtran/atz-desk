"""Circuit breaker mỗi nguồn: failure_threshold lỗi trong window_seconds -> OPEN recovery_seconds -> HALF_OPEN."""
from __future__ import annotations

import time
from collections import deque

from ingestion.log import log

CLOSED, OPEN, HALF_OPEN = "CLOSED", "OPEN", "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int, recovery_seconds: float,
                 window_seconds: float = 60.0, clock=time.monotonic):
        self.name = name
        self.threshold = failure_threshold
        self.recovery = recovery_seconds
        self.window = window_seconds
        self.clock = clock
        self.failures: deque[float] = deque()
        self.opened_at = 0.0
        self._state = CLOSED

    @property
    def state(self) -> str:
        if self._state == OPEN and self.clock() - self.opened_at >= self.recovery:
            self._set(HALF_OPEN, "recovery timeout elapsed")
        return self._state

    def _set(self, state: str, why: str) -> None:
        if state != self._state:
            log("CB", f"source={self.name} {self._state}->{state} ({why})")
            self._state = state

    def allow(self) -> bool:
        return self.state != OPEN

    def success(self) -> None:
        self.failures.clear()
        self._set(CLOSED, "success")

    def failure(self) -> None:
        now = self.clock()
        if self.state == HALF_OPEN:
            self.opened_at = now
            self._set(OPEN, "trial request failed")
            return
        self.failures.append(now)
        while self.failures and now - self.failures[0] > self.window:
            self.failures.popleft()
        log("CB", f"source={self.name} failure {len(self.failures)}/{self.threshold} in {self.window:.0f}s state={self._state}")
        if len(self.failures) >= self.threshold:
            self.opened_at = now
            self.failures.clear()
            self._set(OPEN, f"{self.threshold} failures within {self.window:.0f}s")
