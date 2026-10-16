"""Orchestrator: chia batch, KBS -> VCI, normalize, change detect, cache + publish, degrade."""
from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from ingestion.change_detector import ChangeDetector
from ingestion.circuit_breaker import CircuitBreaker
from ingestion.log import log
from ingestion.normalizer import Quote, normalize_frame
from ingestion.rate_limiter import TokenBucket
from ingestion.sources import SourceAdapter, SourceDown, vnstock_fetch


class Orchestrator:
    def __init__(self, settings, store, fetchers=None, clock=time.monotonic, sleep=time.sleep):
        self.s, self.store = settings, store
        self.tz = ZoneInfo(settings.timezone)
        self.limiter = TokenBucket(settings.safety_max_rpm, settings.limiter_burst,
                                   settings.throttle_warn_ratio, clock=clock, sleep=sleep)
        fetchers = fetchers or {}
        self.sources = [self._adapter(name, fetchers.get(name), clock, sleep)
                        for name in (settings.primary_source, settings.fallback_source)]
        self.detector = ChangeDetector()
        self.degraded = False
        self.metrics = {"cycles": 0, "quotes": 0, "published": 0, "degraded_cycles": 0,
                        "last_ok": None, "last_source": None}

    def _adapter(self, name, fetch, clock, sleep):
        breaker = CircuitBreaker(name, self.s.failure_threshold, self.s.recovery_timeout_seconds,
                                 self.s.breaker_window_seconds, clock=clock)
        return SourceAdapter(name, fetch or vnstock_fetch(name), self.limiter, breaker,
                             self.s.request_timeout_seconds, self.s.retries,
                             self.s.retry_backoff_seconds, self.s.retry_jitter_seconds, sleep=sleep)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def fetch_batch(self, symbols, batch_id) -> list[Quote]:
        for adapter in self.sources:
            if not adapter.breaker.allow():
                log("CB", f"skip source={adapter.name} state={adapter.breaker.state}")
                continue
            try:
                frame, latency = adapter.fetch(symbols)
            except SourceDown as error:
                log("FETCH", f"fallback after {error}")
                continue
            self.metrics["last_source"] = adapter.name
            return normalize_frame(frame, adapter.name, batch_id, latency, self.now())
        raise SourceDown("all sources down")

    def run_cycle(self, symbols=None) -> list[Quote]:
        symbols = list(symbols or self.s.symbols)
        batch_id = "b_" + self.now().strftime("%Y%m%d_%H%M%S")
        fresh, failed = [], []
        for i in range(0, len(symbols), self.s.batch_size):
            chunk = symbols[i:i + self.s.batch_size]
            try:
                fresh.extend(self.fetch_batch(chunk, batch_id))
            except SourceDown:
                failed.extend(chunk)
        self.metrics["cycles"] += 1
        if fresh:
            self.store.save(fresh)
            changed = [q for q in fresh if self.detector.changed(q)]
            self.metrics["published"] += self.store.publish(changed)
            self.metrics["quotes"] += len(fresh)
            self.metrics["last_ok"] = self.now().isoformat(timespec="seconds")
            log("FETCH", f"cycle batch_id={batch_id} quotes={len(fresh)} changed={len(changed)} failed_symbols={len(failed)}")
        stale = self.degrade(failed) if failed else []
        if not failed and self.degraded:
            self.degraded = False
            log("DEGRADE", "recovered: live data again, normal interval")
        return fresh + stale

    def degrade(self, symbols) -> list[Quote]:
        """Cả hai nguồn lỗi: chỉ phục vụ cache, gắn stale=True, tăng interval."""
        if not self.degraded:
            log("DEGRADE", f"entering degraded mode: all sources down for {len(symbols)} symbols")
        self.degraded = True
        self.metrics["degraded_cycles"] += 1
        try:
            cached = [replace(q, stale=True) for q in self.store.load(symbols)]
        except Exception as error:  # noqa: BLE001 - không crash khi Redis cũng lỗi
            log("DEGRADE", f"cache read failed: {error}")
            cached = []
        log("DEGRADE", f"serving cache-only quotes={len(cached)}/{len(symbols)} stale=True next_interval={self.interval():.0f}s")
        return cached

    def in_trading_hours(self) -> bool:
        now = self.now()
        start, end = self.s.trading_hours.split("-")
        return now.weekday() < 5 and start <= now.strftime("%H:%M") <= end

    def interval(self) -> float:
        base = self.s.poll_interval_seconds if self.in_trading_hours() else self.s.off_hours_poll_interval_seconds
        if self.degraded:
            return min(max(base, self.s.poll_interval_seconds * self.s.degraded_interval_multiplier),
                       self.s.degraded_max_interval_seconds)
        return base

    def health(self) -> dict:
        return {
            "ts": self.now().isoformat(timespec="seconds"),
            "epoch": time.time(),
            "mode": "degraded" if self.degraded else "live",
            "breakers": {a.name: a.breaker.state for a in self.sources},
            "limiter": {"granted": self.limiter.granted, "throttled": self.limiter.throttled,
                        "max_rpm": self.s.safety_max_rpm},
            "symbols": len(self.s.symbols),
            **self.metrics,
        }
