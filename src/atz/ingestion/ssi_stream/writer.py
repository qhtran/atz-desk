"""Ghi Redis idx:quote + spark (cùng contract index-feed)."""
from __future__ import annotations

import json
import time
from typing import Any

from ingestion.index.common import IdxQuote
from ingestion.index.series import Spark, in_session, seconds_to_next_session
from ingestion.ssi_stream.config import StreamSettings


class RedisWriter:
    def __init__(self, settings: StreamSettings, redis_client, clock=time.time):
        self.s = settings
        self.r = redis_client
        self.clock = clock
        self.sparks = {
            sym: Spark(sym, settings.timezone, settings.spark_max)
            for sym in ("VNINDEX", "HNXINDEX", "UPCOMINDEX", "VN30")
        }
        self.last: dict[str, IdxQuote] = {}

    def upsert_quote(self, parsed: dict[str, Any]) -> IdxQuote | None:
        sym = parsed["symbol"]
        if sym not in self.sparks:
            return None
        q = IdxQuote(
            sym,
            float(parsed["value"]),
            float(parsed["ref"]),
            "SSI_WS",
            parsed.get("data_time"),
        )
        now = self.clock()
        if in_session(now, self.s.timezone, self.s.sessions):
            self.sparks[sym].add(now, q.value)
        self.last[sym] = q
        pipe = self.r.pipeline()
        pipe.set(
            self.s.quote_key.format(symbol=sym),
            json.dumps({
                "symbol": sym,
                "value": q.value,
                "ref": q.ref,
                "change": q.change,
                "pct": q.pct,
                "ts": now,
                "data_time": q.data_time,
                "source": q.source,
                "contract": None,
            }),
            ex=self.s.quote_ttl,
        )
        ttl = seconds_to_next_session(now, self.s.timezone, self.s.sessions)
        sp = self.sparks[sym]
        if sp.points:
            pipe.set(self.s.spark_key.format(symbol=sym), json.dumps(sp.to_json()), ex=ttl)
        pipe.execute()
        return q
