"""Redis: cache quote:{symbol} (TTL) + Redis Stream publisher + heartbeat health."""
from __future__ import annotations

import json
import time

import redis

from ingestion.log import log
from ingestion.normalizer import Quote


class RedisStore:
    def __init__(self, settings, client=None):
        self.s = settings
        self.r = client or redis.Redis.from_url(settings.redis_url, decode_responses=True,
                                                socket_timeout=5, socket_connect_timeout=5)

    def key(self, symbol: str) -> str:
        return self.s.quote_key.format(symbol=symbol)

    def save(self, quotes: list[Quote]) -> None:
        pipe = self.r.pipeline()
        for q in quotes:
            pipe.set(self.key(q.symbol), json.dumps(q.to_dict()), ex=self.s.quote_ttl_seconds)
        pipe.execute()

    def load(self, symbols) -> list[Quote]:
        values = self.r.mget([self.key(s) for s in symbols]) if symbols else []
        return [Quote(**json.loads(v)) for v in values if v]

    def publish(self, quotes: list[Quote]) -> int:
        pipe = self.r.pipeline()
        for q in quotes:
            fields = {k: ("" if v is None else str(v)) for k, v in q.to_dict().items()}
            pipe.xadd(self.s.stream, fields, maxlen=self.s.stream_maxlen, approximate=True)
        pipe.execute()
        if quotes:
            log("REDIS", f"published stream={self.s.stream} events={len(quotes)}", batch_id=quotes[0].batch_id)
        return len(quotes)

    def write_health(self, payload: dict) -> None:
        self.r.set(self.s.health_key, json.dumps(payload), ex=int(self.s.health_max_age_seconds * 5))

    def redis_health(self) -> dict:
        """redis_health: ping + memory (tài liệu mục 5)."""
        started = time.monotonic()
        self.r.ping()
        mem = self.r.info("memory")
        return {"ping": "PONG", "ping_ms": round((time.monotonic() - started) * 1000, 1),
                "used_memory_human": mem.get("used_memory_human"), "maxmemory_human": mem.get("maxmemory_human"),
                "maxmemory_policy": mem.get("maxmemory_policy")}

    def read_health(self) -> dict | None:
        raw = self.r.get(self.s.health_key)
        return json.loads(raw) if raw else None
