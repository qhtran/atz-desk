"""Vòng lặp index feed: failover provider theo từng mã, spark 1 phút, rollover phái sinh, ghi Redis, health."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ingestion.circuit_breaker import OPEN, CircuitBreaker
from ingestion.index.common import (ERR_IDX_ALL_DOWN, ERR_IDX_FUTURES, ERR_IDX_PROVIDER_OPEN, ERR_IDX_REDIS, FUTURES,
                                    Bucket, ProviderDown, log)
from ingestion.index.providers import REGISTRY
from ingestion.index.series import Spark, in_session, seconds_to_next_session


class IndexFeed:
    def __init__(self, settings, redis_client, providers=None, clock=time.time, mono=time.monotonic):
        self.s, self.r, self.clock = settings, redis_client, clock
        provs = providers if providers is not None else [REGISTRY[n](settings) for n in settings.providers
                                                           if settings.provider_settings.get(n, {}).get("enabled", True)]
        self.providers = []
        for p in provs:
            ps = settings.provider_settings.get(p.name, {})
            self.providers.append({
                "p": p, "bucket": Bucket(float(ps.get("rpm", 30)), clock=mono, burst=ps.get("burst")),
                "cb": CircuitBreaker(p.name, int(ps.get("failure_threshold", 3)), float(ps.get("recovery_seconds", 60)),
                                     float(ps.get("window_seconds", 60)), clock=mono),
                "errors": 0, "last_ok": None, "skipped": 0,
            })
        self.sparks = {s: Spark(s, settings.timezone, settings.spark_max) for s in settings.symbols}
        self.last: dict = {}            # sym -> IdxQuote
        self.last_ok_epoch: dict = {}   # sym -> epoch lần lấy thành công gần nhất
        self.cycles = 0
        self.down_logged: set = set()
        self.last_resolve = 0.0

    # ------------------------------------------------------------- providers
    def _usable(self, e) -> bool:
        p = e["p"]
        if not p.enabled:
            return False
        if not e["cb"].allow():
            if e.get("logged_open") is not True:
                e["logged_open"] = True
                log("CB", f"provider {p.name} circuit OPEN, skip to next provider", logging.WARNING,
                    error_code=ERR_IDX_PROVIDER_OPEN, source=p.name, circuit_state=OPEN)
            return False
        e["logged_open"] = False
        return True

    def _call(self, e, method: str, symbols, *args):
        p = e["p"]
        if not e["bucket"].try_acquire(p.cost(symbols)):
            e["skipped"] += 1
            raise ProviderDown(f"{p.name} local rate limit")
        t0 = time.monotonic()
        try:
            res = getattr(p, method)(symbols, *args)
        except ProviderDown:
            e["errors"] += 1
            e["cb"].failure()
            raise
        except Exception as err:  # noqa: BLE001 - provider lạ không được làm chết vòng lặp
            e["errors"] += 1
            e["cb"].failure()
            raise ProviderDown(f"{p.name} {type(err).__name__}: {err}") from None
        e["cb"].success()
        e["last_ok"] = self.clock()
        e["latency_ms"] = int((time.monotonic() - t0) * 1000)
        return res

    def fetch(self, method: str, symbols, *args) -> dict:
        """Thử lần lượt provider; mã nào provider trước thiếu thì hỏi provider sau."""
        need, got = list(symbols), {}
        for e in self.providers:
            if not need:
                break
            if not self._usable(e):
                continue
            try:
                res = self._call(e, method, need, *args)
            except ProviderDown as err:
                if "local rate limit" in str(err):
                    continue   # hết token cục bộ: chuyển provider sau, không log mỗi 3s (đếm ở health.skipped)
                log("FETCH", f"{method} via {e['p'].name} failed: {err}", source=e["p"].name,
                    circuit_state=e["cb"].state)
                continue
            res = {k: v for k, v in res.items() if v}
            got.update(res)
            need = [s for s in need if s not in res]
        return got

    # ------------------------------------------------------------- futures
    def contracts(self) -> dict:
        for e in self.providers:
            c = getattr(e["p"], "contracts", None)
            if c:
                return c
        return {}

    def maybe_resolve(self) -> None:
        now = self.clock()
        c = self.contracts()
        today = datetime.fromtimestamp(now, ZoneInfo(self.s.timezone)).date().isoformat()
        expired = any((c.get(f) or {}).get("maturity") and c[f]["maturity"] < today for f in FUTURES)
        if not expired and now - self.last_resolve < self.s.futures_resolve_seconds:
            return
        self.last_resolve = now
        for e in self.providers:
            if hasattr(e["p"], "resolve_futures") and self._usable(e):
                try:
                    self._call(e, "resolve_futures_wrapped", list(FUTURES))
                    log("FUTURES", f"contracts {e['p'].contracts}", source=e["p"].name)
                    return
                except ProviderDown as err:
                    log("FUTURES", f"resolve failed: {err}", logging.WARNING, error_code=ERR_IDX_FUTURES, source=e["p"].name)

    # ------------------------------------------------------------- vòng lặp
    def backfill(self) -> None:
        since = int(self.clock()) - 86400 * self.s.lookback_days
        bars = self.fetch("bars", self.s.symbols, since)
        c = self.contracts()
        for sym, pts in bars.items():
            self.sparks[sym].load(pts, (c.get(sym) or {}).get("code"))
        log("BACKFILL", "loaded " + ", ".join(f"{s}={len(self.sparks[s].points)}" for s in self.s.symbols))
        self.write_sparks()

    def stream_healthy(self) -> bool:
        """True khi atz-ssi-stream đang primary (ADR 0008) — index-feed không ghi đè spot bằng SSI REST."""
        if not self.s.stream_backup_enabled:
            return False
        try:
            raw = self.r.get(self.s.stream_health_key)
        except Exception:  # noqa: BLE001
            return False
        if not raw:
            return False
        try:
            h = json.loads(raw)
        except (TypeError, ValueError):
            return False
        if not h.get("healthy"):
            return False
        age = self.clock() - float(h.get("epoch") or 0)
        return age <= self.s.stream_max_age

    def _read_redis_quote(self, sym: str):
        try:
            raw = self.r.get(self.s.quote_key.format(symbol=sym))
            if not raw:
                return None
            d = json.loads(raw)
            from ingestion.index.common import IdxQuote
            return IdxQuote(sym, float(d["value"]), float(d["ref"]), str(d.get("source") or "SSI_WS"),
                            d.get("data_time"), d.get("contract"))
        except Exception:  # noqa: BLE001
            return None

    def cycle(self) -> dict:
        self.cycles += 1
        now = self.clock()
        self.maybe_resolve()
        stream_ok = self.stream_healthy()
        spot = set(self.s.stream_spot_symbols)
        # Khi WS healthy: chỉ REST-fetch futures (+ spot thiếu); không gọi SSI cho spot (tránh đè SSI_WS)
        if stream_ok:
            # Spot do ssi-stream ghi; REST chỉ lấy futures (và mã ngoài spot list)
            fetch_syms = [s for s in self.s.symbols if s not in spot]
            quotes = self.fetch("quotes", fetch_syms) if fetch_syms else {}
            for sym in self.s.symbols:
                if sym in spot and sym not in quotes:
                    rq = self._read_redis_quote(sym)
                    if rq:
                        quotes[sym] = rq
        else:
            quotes = self.fetch("quotes", self.s.symbols)

        rebackfill = []
        for sym, q in quotes.items():
            sp = self.sparks[sym]
            if sym in FUTURES and sp.roll_if_needed(q.contract):
                log("ROLLOVER", f"{sym} contract -> {q.contract}, series reset", symbol=sym)
                rebackfill.append(sym)
            if in_session(now, self.s.timezone, self.s.sessions):
                # Spot đã do stream cập nhật spark — tránh double-add khi đọc lại Redis cùng phút
                if not (stream_ok and sym in spot and str(q.source).startswith("SSI_WS")):
                    sp.add(now, q.value)
            self.last[sym] = q
            self.last_ok_epoch[sym] = now
        missing = [s for s in self.s.symbols if s not in quotes]
        for s in missing:
            if s not in self.down_logged:
                log("FETCH", f"no provider returned {s}; keeping last value (stale after 120s)", logging.WARNING,
                    error_code=ERR_IDX_ALL_DOWN, symbol=s)
                self.down_logged.add(s)
        self.down_logged -= set(quotes)
        if rebackfill:
            for sym, pts in self.fetch("bars", rebackfill, int(now) - 86400).items():
                self.sparks[sym].load(pts, self.sparks[sym].contract)
        # Không ghi đè spot Redis khi stream đang primary (stream đã SET)
        to_write = {k: v for k, v in quotes.items() if not (stream_ok and k in spot)}
        self.write(to_write, now)
        return quotes

    def write(self, quotes: dict, now: float) -> None:
        try:
            pipe = self.r.pipeline()
            for sym, q in quotes.items():
                pipe.set(self.s.quote_key.format(symbol=sym), json.dumps({
                    "symbol": sym, "value": q.value, "ref": q.ref, "change": q.change, "pct": q.pct,
                    "ts": now, "data_time": q.data_time, "source": q.source, "contract": q.contract}), ex=self.s.quote_ttl)
            pipe.execute()
            self.write_sparks()
        except Exception as err:  # noqa: BLE001
            log("REDIS", f"write failed: {type(err).__name__}: {err}", logging.ERROR, error_code=ERR_IDX_REDIS)

    def write_sparks(self) -> None:
        ttl = seconds_to_next_session(self.clock(), self.s.timezone, self.s.sessions)
        try:
            pipe = self.r.pipeline()
            for sym, sp in self.sparks.items():
                if sp.points:
                    pipe.set(self.s.spark_key.format(symbol=sym), json.dumps(sp.to_json()), ex=ttl)
            pipe.execute()
        except Exception as err:  # noqa: BLE001
            log("REDIS", f"spark write failed: {type(err).__name__}: {err}", logging.ERROR, error_code=ERR_IDX_REDIS)

    def interval(self) -> float:
        return self.s.poll_trading if in_session(self.clock(), self.s.timezone, self.s.sessions) else self.s.poll_off

    def health(self) -> dict:
        now = self.clock()
        return {"epoch": now, "ts": datetime.fromtimestamp(now, ZoneInfo(self.s.timezone)).isoformat(timespec="seconds"), "cycles": self.cycles,
                "fresh": sum(1 for s in self.s.symbols if now - self.last_ok_epoch.get(s, 0) <= self.s.health_max_age),
                "symbols": len(self.s.symbols),
                "ssi_stream_primary": self.stream_healthy(),
                "providers": {e["p"].name: {"enabled": e["p"].enabled, "circuit": e["cb"].state, "errors": e["errors"],
                                            "skipped": e["skipped"], "rpm_granted": e["bucket"].granted,
                                            "latency_ms": e.get("latency_ms")} for e in self.providers},
                "sources": {s: q.source for s, q in self.last.items()},
                "contracts": {k: v.get("code") for k, v in self.contracts().items()}}

    def write_health(self) -> None:
        try:
            self.r.set(self.s.health_key, json.dumps(self.health()), ex=3600)
        except Exception as err:  # noqa: BLE001
            log("REDIS", f"health write failed: {err}", logging.ERROR, error_code=ERR_IDX_REDIS)
