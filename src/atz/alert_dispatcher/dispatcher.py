"""Alert Dispatcher: signal -> dedup -> signal_history -> in-app -> broadcast + kênh user (Telegram ưu tiên, fallback Email)."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime

import redis

from alert_dispatcher import prefs as P
from alert_dispatcher import store
from alert_dispatcher.adapters import ChannelError, EmailAdapter, InAppAdapter, TelegramAdapter, format_text
from alert_dispatcher.circuit import Circuit
from alert_dispatcher.consumer import SignalConsumer
from alert_dispatcher.log import (ERR_CIRCUIT, ERR_EMAIL, ERR_PREF, ERR_RATE, ERR_SYS_SQLITE, ERR_TELEGRAM, TZ, log)
from alert_dispatcher.ratelimit import RateLimiter

ERR_BY_CHANNEL = {"telegram": ERR_TELEGRAM, "email": ERR_EMAIL}
FIELDS = ("signal_id", "user_id", "symbol", "timestamp", "filter_name", "direction", "price", "reason", "confidence")


def parse(fields: dict) -> dict:
    raw = fields.get("data") or fields.get("signal")
    sig = json.loads(raw) if raw else dict(fields)
    missing = [f for f in FIELDS if f not in sig]
    if missing:
        raise ValueError(f"signal thiếu trường {missing}")
    sig["price"], sig["confidence"], sig["user_id"] = float(sig["price"]), float(sig["confidence"]), str(sig["user_id"])
    return sig


class Dispatcher:
    def __init__(self, cfg, r=None, db=None, adapters=None, clock=time.time):
        self.cfg, ad = cfg, cfg["alert_dispatcher"]
        self.ad, self.clock = ad, clock
        self.r = r or redis.Redis.from_url(cfg["redis"]["url"], decode_responses=True, socket_timeout=10)
        self.db = db or store.open_db(cfg["sqlite"]["path"])
        ch = ad["channels"]
        self.enabled = {n: bool(ch[n]["enabled"]) for n in ("telegram", "email", "inapp")}
        adapters = adapters or {}
        self.adapters = {}
        if self.enabled["telegram"]:
            self.adapters["telegram"] = adapters.get("telegram") or TelegramAdapter(ch["telegram"]["timeout_seconds"], ch["telegram"]["retries"])
        if self.enabled["email"]:
            self.adapters["email"] = adapters.get("email") or EmailAdapter(ch["email"]["timeout_seconds"], ch["email"]["retries"], ch["email"].get("sender_email"), ch["email"].get("sender_name"))
        self.inapp = InAppAdapter(self.r, ch["inapp"]["max_per_user"])
        c = ad["circuit"]
        self.circuits = {n: Circuit(n, c["failure_threshold"], c["window_seconds"], c["open_seconds"]) for n in self.adapters}
        self.limiter = RateLimiter(self.r, ad["rate_limit"]["windows"], clock=clock)
        self.broadcast = [str(x) for x in ch["telegram"].get("broadcast_chat_ids") or []] if self.enabled["telegram"] else []
        self.default_quiet = ad["quiet_hours"].get("default")
        # signal riêng tư (vd vị thế Module 4: pos_*) -> KHÔNG gửi channel broadcast
        self.private_prefixes = tuple(ch["telegram"].get("private_filter_prefixes", ["pos_"]) or [])
        self.consumer = SignalConsumer(self.r, ad["consumer"]["stream"], ad["consumer"]["group"], ad["consumer"]["consumer_name"],
                                       ad["consumer"]["read_count"], ad["consumer"]["block_ms"],
                                       ad["consumer"]["claim_min_idle_ms"], ad["consumer"]["claim_every_seconds"])
        self.stats = {n: {"sent": 0, "failed": 0} for n in ("telegram", "email", "inapp")}
        self.processed = 0
        self._pref_warned: dict[str, float] = {}

    # ---- kênh -----------------------------------------------------------
    def _send(self, channel, sig, hist_id, target, call) -> bool:
        uid = sig["user_id"]
        circ = self.circuits[channel]
        if not circ.allow():
            log("ROUTE", f"{channel} circuit open, skip target", error_code=ERR_CIRCUIT, symbol=sig["symbol"], user_id=uid,
                channel=channel, circuit_state=circ.state, signal_id=sig["signal_id"])
            self._log_delivery(sig, hist_id, channel, target, "skipped", ERR_CIRCUIT, "circuit open")
            return False
        t0 = time.monotonic()
        try:
            provider_id = call()
        except ChannelError as e:
            ms = int((time.monotonic() - t0) * 1000)
            opened = circ.failure()
            self.stats[channel]["failed"] += 1
            log("SEND", f"{channel} send failed: {e}", logging.ERROR, error_code=ERR_BY_CHANNEL[channel], symbol=sig["symbol"],
                user_id=uid, latency_ms=ms, channel=channel, circuit_state=circ.state, signal_id=sig["signal_id"])
            if opened:
                log("CIRCUIT", f"{channel} circuit OPEN", logging.ERROR, error_code=ERR_CIRCUIT, channel=channel, circuit_state=circ.state)
            self._log_delivery(sig, hist_id, channel, target, "failed", ERR_BY_CHANNEL[channel], str(e), ms)
            return False
        ms = int((time.monotonic() - t0) * 1000)
        was = circ.state
        circ.success()
        if was != "closed":
            log("CIRCUIT", f"{channel} circuit CLOSED", channel=channel, circuit_state="closed")
        self.stats[channel]["sent"] += 1
        log("SEND", f"{channel} sent", symbol=sig["symbol"], user_id=uid, latency_ms=ms, channel=channel, signal_id=sig["signal_id"])
        self._log_delivery(sig, hist_id, channel, target, "sent", latency_ms=ms, provider_id=provider_id)
        return True

    def _log_delivery(self, sig, hist_id, channel, target, status, code=None, err=None, latency_ms=None, provider_id=None):
        try:
            store.log_delivery(self.db, sig, hist_id, channel, _mask(channel, target), status, code, err, latency_ms, provider_id)
        except Exception as e:  # noqa: BLE001
            log("TRACK", f"delivery log failed: {e}", logging.ERROR, error_code=ERR_SYS_SQLITE, signal_id=sig["signal_id"])

    def _telegram(self, sig, hist_id, chat_id) -> bool:
        text = format_text(sig)
        return self._send("telegram", sig, hist_id, chat_id, lambda: self.adapters["telegram"].send(chat_id, text))

    def _email(self, sig, hist_id, to) -> bool:
        subject = f"[atz.vn] {sig['symbol']} {sig['direction']} ({sig['filter_name']})"
        text = format_text(sig)
        return self._send("email", sig, hist_id, to, lambda: self.adapters["email"].send(to, subject, text))

    # ---- xử lý 1 signal -----------------------------------------------
    def handle(self, sig: dict) -> dict:
        uid, now = sig["user_id"], datetime.fromtimestamp(self.clock(), TZ)
        out = {"signal_id": sig["signal_id"], "user": [], "broadcast": []}
        if not self.r.set(f"alert:dedup:{sig['signal_id']}", 1, nx=True, ex=self.ad["dedup"]["window_seconds"]):
            log("DEDUP", "duplicate signal_id skipped", symbol=sig["symbol"], user_id=uid, signal_id=sig["signal_id"])
            out["dedup"] = True
            return out
        hist_id = None
        try:
            hist_id = store.record_history(self.db, sig)
        except Exception as e:  # noqa: BLE001
            log("TRACK", f"signal_history write failed: {e}", logging.ERROR, error_code=ERR_SYS_SQLITE, signal_id=sig["signal_id"])
        try:
            self.inapp.send(uid, sig)
            self.stats["inapp"]["sent"] += 1
            self._log_delivery(sig, hist_id, "inapp", uid, "sent")
        except Exception as e:  # noqa: BLE001
            self.stats["inapp"]["failed"] += 1
            log("SEND", f"inapp failed: {e}", logging.ERROR, error_code="ERR-SYS-001", user_id=uid, signal_id=sig["signal_id"])
        out["broadcast"] = self._broadcast(sig, hist_id, now)
        out["user"] = self._user(sig, hist_id, now)
        if any(x == "sent" for x in out["broadcast"] + out["user"]):
            store.mark_notified(self.db, hist_id)
        return out

    def _broadcast(self, sig, hist_id, now) -> list[str]:
        if not self.broadcast:
            return []
        if self.private_prefixes and str(sig["filter_name"]).startswith(self.private_prefixes):
            log("ROUTE", "private signal, broadcast skipped", symbol=sig["symbol"], user_id=sig["user_id"], signal_id=sig["signal_id"])
            return ["private"]
        key = f"alert:bdedup:{sig['symbol']}:{sig['filter_name']}:{sig['direction']}"
        if not self.r.set(key, 1, nx=True, ex=600):   # cùng mã+filter+chiều từ nhiều user -> 1 tin channel / 10 phút
            return ["dup"]
        if P.in_quiet(self.default_quiet, now):
            log("ROUTE", "broadcast quiet hours, skip", symbol=sig["symbol"], signal_id=sig["signal_id"])
            return ["quiet"]
        ok, win = self.limiter.hit("broadcast")
        if not ok:
            log("RATE", f"broadcast rate limit {win}", error_code=ERR_RATE, symbol=sig["symbol"], user_id="broadcast", signal_id=sig["signal_id"])
            self._log_delivery(sig, hist_id, "telegram", "broadcast", "skipped", ERR_RATE, win)
            return ["rate"]
        return ["sent" if self._telegram(sig, hist_id, c) else "failed" for c in self.broadcast]

    def _user(self, sig, hist_id, now) -> list[str]:
        uid = sig["user_id"]
        try:
            user = store.get_user(self.db, uid)
        except Exception as e:  # noqa: BLE001
            log("PREF", f"user read failed: {e}", logging.ERROR, error_code=ERR_SYS_SQLITE, user_id=uid)
            return ["error"]
        p = P.resolve(user, sig, self.default_quiet)
        chans = [c for c in p.channels if c in self.adapters]
        if not p.found or not chans:
            if self.clock() - self._pref_warned.get(uid, -1e12) > 3600:   # 1 cảnh báo / user / giờ
                self._pref_warned[uid] = self.clock()
                log("PREF", "no external channel configured (in-app only)" + ("" if p.found else "; user not in DB"),
                    error_code=ERR_PREF, user_id=uid, symbol=sig["symbol"])
            return ["nopref"]
        if not p.wants:
            return ["filtered"]
        if P.in_quiet(p.quiet_hours, now):
            log("ROUTE", "user quiet hours, external skipped (in-app kept)", user_id=uid, symbol=sig["symbol"], signal_id=sig["signal_id"])
            self._log_delivery(sig, hist_id, chans[0], None, "skipped", None, "quiet hours")
            return ["quiet"]
        ok, win = self.limiter.hit(uid)
        if not ok:
            log("RATE", f"user rate limit {win}", error_code=ERR_RATE, user_id=uid, symbol=sig["symbol"], signal_id=sig["signal_id"])
            self._log_delivery(sig, hist_id, chans[0], None, "skipped", ERR_RATE, win)
            return ["rate"]
        order = [self.ad["routing"]["primary"]] + list(self.ad["routing"]["fallback"])
        for ch in [c for c in order if c in chans]:
            sent = self._telegram(sig, hist_id, p.telegram_chat_id) if ch == "telegram" else self._email(sig, hist_id, p.email)
            if sent:
                return [f"sent"]
            log("ROUTE", f"{ch} failed -> fallback", user_id=uid, symbol=sig["symbol"], signal_id=sig["signal_id"])
        return ["failed"]

    # ---- vòng lặp ---------------------------------------------------------
    def step(self) -> int:
        batch = self.consumer.read()
        for mid, fields in batch:
            t0 = time.monotonic()
            try:
                sig = parse(fields)
                res = self.handle(sig)
                log("DISPATCH", f"done {json.dumps({k: v for k, v in res.items() if k != 'signal_id'})}", symbol=sig["symbol"],
                    user_id=sig["user_id"], latency_ms=int((time.monotonic() - t0) * 1000), signal_id=sig["signal_id"])
            except ValueError as e:
                log("CONSUME", f"bad signal {mid}: {e}", logging.WARNING)
            self.consumer.ack([mid])
            self.processed += 1
        return len(batch)

    def health(self) -> dict:
        rate = {}
        for n, s in self.stats.items():
            tot = s["sent"] + s["failed"]
            rate[n] = {**s, "success_rate": round(s["sent"] / tot, 3) if tot else None,
                       "enabled": self.enabled[n], "circuit": self.circuits[n].state if n in self.circuits else ("n/a" if n == "inapp" else "disabled")}
        return {"epoch": time.time(), "processed": self.processed, "lag": self.consumer.lag(), "channels": rate}

    def write_health(self) -> dict:
        beat = self.health()
        self.r.set(self.ad["health"]["key"], json.dumps(beat), ex=3600)
        return beat


def _mask(channel, target):
    if target is None or channel != "email":
        return target
    s = str(target)
    name, _, dom = s.partition("@")
    return (name[:2] + "***@" + dom) if dom else "***"
