"""Orchestrator của Module 2: consume -> resolve -> evaluate -> dedup -> publish -> ack, kèm backpressure + health."""
from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

import redis

from filter_runner.consumer import QuoteConsumer
from filter_runner.contracts import DIRECTIONS, Signal, new_signal_id
from filter_runner.dedup import Deduplicator
from filter_runner.evaluator import Evaluator, FilterCircuit
from filter_runner.history import HistoryCache
from filter_runner.log import log
from filter_runner.publisher import SignalPublisher
from filter_runner.registry import FilterRegistry
from filter_runner.resolver import UserFilterResolver

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def confidence(result) -> float:
    details = result.details or {}
    if details.get("total"):
        value = float(details.get("score", 0)) / float(details["total"])
    else:
        value = float(result.strength if result.strength is not None else 1.0)
    return round(min(1.0, max(0.0, value)), 2)


class FilterRunner:
    def __init__(self, cfg: dict, r=None, registry=None, history=None, resolver=None, clock=time.monotonic):
        fr = cfg["filter_runner"]
        self.cfg, self.fr, self.clock = cfg, fr, clock
        self.r = r or redis.Redis.from_url(cfg["redis"]["url"], decode_responses=True,
                                           socket_timeout=10, socket_connect_timeout=5)
        c = fr["consumer"]
        self.consumer = QuoteConsumer(self.r, c["stream"], c["group"], c["consumer_name"], c["read_count"],
                                      c["block_ms"], c["claim_min_idle_ms"], c["claim_every_seconds"], clock=clock)
        self.registry = registry or FilterRegistry()
        h = fr["history"]
        self.history = history or HistoryCache(h["days"], h["cache_ttl_seconds"], h["quote_price_scale"],
                                               remote=h["remote_fetch"], clock=clock)
        rs = fr["resolver"]
        self.resolver = resolver or UserFilterResolver(cfg["sqlite"]["path"], rs["default_filters"],
                                                       rs["default_user_id"], rs["cache_ttl_seconds"], clock=clock)
        fc = fr["filter_circuit"]
        self.circuit = FilterCircuit(fc["failure_threshold"], fc["window_seconds"], fc["disable_seconds"], clock=clock)
        self.evaluator = Evaluator(fr["evaluator"]["timeout_seconds"], fr["evaluator"]["max_workers"], self.circuit)
        d = fr["dedup"]
        self.dedup = Deduplicator(self.r, d["window_seconds"], d["key"], d["fail_open"])
        self.publisher = SignalPublisher(self.r, fr["publisher"]["stream"], fr["publisher"]["maxlen"])
        self.signal_times: deque[float] = deque()
        self.metrics = {"events": 0, "acked": 0, "evaluations": 0, "signals": 0, "duplicates": 0,
                        "errors": 0, "coalesced": 0, "last_event": None, "lag": 0}

    # --- một quote ---
    def process_quote(self, quote: dict) -> list[Signal]:
        symbol = str(quote.get("symbol") or "").upper()
        if not symbol or str(quote.get("stale", "")).lower() == "true":
            return []   # quote stale (degraded) không dùng để phát tín hiệu
        plans = self.resolver.plans()
        flows = {i["name"] for items in plans.values() for i in items if i["kind"] == "filter"}
        base = self.history.base(symbol, flows)
        if base is None or base.empty:
            log("EVAL", "skip: no history bars", logging.WARNING, symbol=symbol)
            return []
        bars = self.history.with_quote(base, quote)
        index_bars = None
        memo: dict = {}
        out: list[Signal] = []
        for user_id, items in plans.items():
            for item in items:
                if item["kind"] == "composite" and index_bars is None:
                    index_bars = self.history.index_bars()
                fn = self.registry.job(item, index_bars)
                if fn is None:
                    continue
                key = (item["kind"], item["name"], json.dumps(item.get("params") or item.get("definition"), sort_keys=True))
                started = time.monotonic()
                result = self.evaluator.run(item["name"], fn, bars, symbol, key, memo)
                self.metrics["evaluations"] += 1
                if result is None or not result.matched or result.signal_type not in DIRECTIONS:
                    continue
                direction = DIRECTIONS[result.signal_type]
                if not self.dedup.first_seen(user_id, symbol, item["name"], direction):
                    self.metrics["duplicates"] += 1
                    continue
                signal = Signal(signal_id=new_signal_id(), user_id=str(user_id), symbol=symbol,
                                timestamp=datetime.now(TZ).isoformat(timespec="seconds"), filter_name=item["name"],
                                direction=direction, price=float(quote["price"]), reason=result.reason,
                                confidence=confidence(result))
                self.publisher.publish(signal)
                self.signal_times.append(self.clock())
                self.metrics["signals"] += 1
                out.append(signal)
                log("EVAL", f"match {direction} reason={result.reason}", symbol=symbol, user_id=str(user_id),
                    filter_name=item["name"], latency_ms=int((time.monotonic() - started) * 1000))
        return out

    # --- một vòng đọc ---
    def step(self) -> int:
        batch = self.consumer.read()
        if not batch:
            return 0
        lag = self.consumer.lag()
        self.metrics["lag"] = lag
        latest: dict[str, tuple[str, dict]] = {}
        ordered = []
        if lag > self.fr["backpressure"]["lag_threshold"]:
            for msg_id, fields in batch:   # chỉ giữ quote mới nhất mỗi mã
                latest[fields.get("symbol", "")] = (msg_id, fields)
            ordered = list(latest.values())
            skipped = len(batch) - len(ordered)
            self.metrics["coalesced"] += skipped
            log("BACKPRESSURE", f"lag={lag} > {self.fr['backpressure']['lag_threshold']}: coalesced {len(batch)} -> {len(ordered)} (latest per symbol)",
                logging.WARNING)
        else:
            ordered = batch
        for msg_id, fields in ordered:
            started = time.monotonic()
            try:
                self.process_quote(fields)
            except Exception as error:  # noqa: BLE001 - 1 event lỗi không chặn stream
                self.metrics["errors"] += 1
                log("EVAL", f"event failed: {type(error).__name__}: {error}", logging.ERROR,
                    symbol=fields.get("symbol"), stream_id=msg_id)
            self.metrics["last_event"] = fields.get("timestamp")
        ids = [i for i, _ in batch]
        self.consumer.ack(ids)        # ack cả message đã coalesce (đã thay bằng bản mới hơn)
        self.metrics["events"] += len(batch)
        self.metrics["acked"] += len(ids)
        log("CONSUME", f"acked={len(ids)} processed={len(ordered)} lag={lag}")
        return len(batch)

    def signals_per_minute(self) -> int:
        now = self.clock()
        while self.signal_times and now - self.signal_times[0] >= 60:
            self.signal_times.popleft()
        return len(self.signal_times)

    def health(self) -> dict:
        disabled = self.circuit.disabled()
        return {"ts": datetime.now(TZ).isoformat(timespec="seconds"), "epoch": time.time(),
                "signals_per_minute": self.signals_per_minute(), "disabled_filters": len(disabled),
                "disabled_filter_names": disabled, "filters_loaded": len(self.registry.names()),
                "users": len(self.resolver.plans()), **self.metrics}

    def write_health(self) -> dict:
        beat = self.health()
        h = self.fr["health"]
        self.r.set(h["key"], json.dumps(beat, ensure_ascii=False), ex=int(h["max_age_seconds"] * 5))
        return beat
