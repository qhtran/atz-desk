"""Rate limit per user trên Redis (sorted set, sliding window): mặc định 10/5min và 30/hour."""
from __future__ import annotations

import time
import uuid


class RateLimiter:
    def __init__(self, r, windows, clock=time.time):
        self.r, self.windows, self.clock = r, [(int(w["seconds"]), int(w["max"])) for w in windows], clock

    def hit(self, user_id: str) -> tuple[bool, str | None]:
        """Trả (cho_phép, window_bị_chặn). Chỉ tính khi được phép."""
        now = self.clock()
        for sec, mx in self.windows:
            key = f"alert:rl:{user_id}:{sec}"
            self.r.zremrangebyscore(key, 0, now - sec)
            if self.r.zcard(key) >= mx:
                return False, f"{mx}/{sec}s"
        for sec, _ in self.windows:
            key = f"alert:rl:{user_id}:{sec}"
            self.r.zadd(key, {uuid.uuid4().hex: now})
            self.r.expire(key, sec + 60)
        return True, None
