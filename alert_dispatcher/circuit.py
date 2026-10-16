"""Circuit breaker per channel: lỗi >= threshold trong window -> open trong open_seconds, rồi half-open thử 1 lần."""
from __future__ import annotations

import time


class Circuit:
    def __init__(self, name, threshold, window, open_seconds, clock=time.monotonic):
        self.name, self.threshold, self.window, self.open_seconds, self.clock = name, threshold, window, open_seconds, clock
        self.failures: list[float] = []
        self.opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if self.clock() - self.opened_at >= self.open_seconds else "open"

    def allow(self) -> bool:
        return self.state != "open"

    def success(self) -> None:
        self.failures.clear()
        self.opened_at = None

    def failure(self) -> bool:
        """Ghi lỗi; trả True nếu vừa chuyển sang open."""
        now = self.clock()
        if self.state == "half_open":
            self.opened_at = now
            return True
        self.failures = [t for t in self.failures if now - t < self.window] + [now]
        if len(self.failures) >= self.threshold and self.opened_at is None:
            self.opened_at = now
            return True
        return False
