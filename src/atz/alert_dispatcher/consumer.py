"""Event Consumer: consumer group trên stream:signals, ack, khôi phục pending (XAUTOCLAIM), đo lag cho backpressure."""
from __future__ import annotations

import logging
import time

import redis

from alert_dispatcher.log import ERR_SYS_REDIS, log


class SignalConsumer:
    def __init__(self, r, stream: str, group: str, name: str, count: int, block_ms: int,
                 claim_idle_ms: int, claim_every: float, clock=time.monotonic):
        self.r, self.stream, self.group, self.name = r, stream, group, name
        self.count, self.block_ms = count, block_ms
        self.claim_idle_ms, self.claim_every, self.clock = claim_idle_ms, claim_every, clock
        self._last_claim = -1e9
        self.ensure_group()

    def ensure_group(self) -> None:
        try:
            self.r.xgroup_create(self.stream, self.group, id="$", mkstream=True)
            log("CONSUME", f"group created stream={self.stream} group={self.group}")
        except redis.exceptions.ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    def recover_pending(self) -> list[tuple[str, dict]]:
        """Lấy lại message pending quá lâu của consumer đã chết (hoặc của chính mình trước khi restart)."""
        if self.clock() - self._last_claim < self.claim_every:
            return []
        self._last_claim = self.clock()
        _next, claimed, *_ = self.r.xautoclaim(self.stream, self.group, self.name, self.claim_idle_ms,
                                               start_id="0-0", count=self.count)
        claimed = [(i, f) for i, f in claimed if f]
        if claimed:
            log("CONSUME", f"recovered pending messages={len(claimed)} idle>={self.claim_idle_ms}ms")
        return claimed

    def read(self) -> list[tuple[str, dict]]:
        try:
            batch = self.recover_pending()
            if batch:
                return batch
            resp = self.r.xreadgroup(self.group, self.name, {self.stream: ">"}, count=self.count, block=self.block_ms)
        except redis.exceptions.ConnectionError as error:
            log("CONSUME", f"redis connection failed: {error}", logging.ERROR, error_code=ERR_SYS_REDIS)
            time.sleep(2)
            return []
        except redis.exceptions.ResponseError as error:
            if "NOGROUP" in str(error):   # stream bị xoá/tạo lại
                self.ensure_group()
                return []
            raise
        return [(i, f) for _s, entries in (resp or []) for i, f in entries]

    def ack(self, ids) -> None:
        if ids:
            self.r.xack(self.stream, self.group, *ids)

    def lag(self) -> int:
        """pending + chưa giao (lag) của group."""
        try:
            info = next(g for g in self.r.xinfo_groups(self.stream) if g["name"] == self.group)
            return int(info.get("pending") or 0) + int(info.get("lag") or 0)
        except Exception:  # noqa: BLE001
            return 0
