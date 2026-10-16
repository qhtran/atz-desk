"""Live Position Monitor: Price Subscriber -> P&L Calculator -> Threshold Evaluator -> Alert Bridge (stream:signals).

- Event từ stream:quotes (consumer group riêng) + sweep định kỳ đọc quote:{symbol} (timeout đọc giá).
- Stale: quote cũ / quote.stale / ingestion degraded hoặc mất heartbeat -> đánh dấu stale, KHÔNG cảnh báo (ERR-POS-001).
- SL/TP: trigger 1 lần / vị thế (positions.sl_hit_at/tp_hit_at, atomic). Biến động: Redis SET NX theo cửa sổ dedup.
- Cảnh báo đi qua Module 3 bằng Signal contract -> rate limit, quiet hours, channel + chat riêng y như signal filter.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime

import redis

from position_monitor import store
from position_monitor.log import ERR_PNL, ERR_STALE, ERR_SYS_REDIS, ERR_SYS_SQLITE, TZ, log
from position_monitor.pnl import PnlError, calc, parse_quote


class Monitor:
    def __init__(self, cfg, r=None, db=None, clock=time.time):
        self.cfg, self.pm, self.clock = cfg, cfg["position_monitor"], clock
        tmo = float(self.pm["price_read_timeout_seconds"])
        self.r = r or redis.Redis.from_url(cfg["redis"]["url"], decode_responses=True, socket_timeout=tmo,
                                           socket_connect_timeout=tmo)
        self.db = db or store.open_db(cfg["sqlite"]["path"])
        c = self.pm["consumer"]
        self.stream, self.group, self.name = c["stream"], c["group"], c["consumer_name"]
        self._ensure_group()
        self.positions: list[dict] = []
        self._loaded_at = -1e18
        self._last_sweep = -1e18
        self._last_claim = -1e18
        self._stale_logged: dict[str, float] = {}
        self._prices: dict[str, deque] = defaultdict(deque)   # symbol -> (epoch, price) trong cửa sổ biến động
        self.metrics = {"events": 0, "evaluations": 0, "alerts": 0, "stale_marks": 0, "pnl_errors": 0, "errors": 0}

    # ---- Redis consumer -------------------------------------------------
    def _ensure_group(self):
        try:
            self.r.xgroup_create(self.stream, self.group, id="$", mkstream=True)
            log("CONSUME", f"group created stream={self.stream} group={self.group}")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def _read(self) -> list[tuple[str, dict]]:
        c = self.pm["consumer"]
        try:
            if self.clock() - self._last_claim >= c["claim_every_seconds"]:
                self._last_claim = self.clock()
                _n, claimed, *_ = self.r.xautoclaim(self.stream, self.group, self.name, c["claim_min_idle_ms"],
                                                    start_id="0-0", count=c["read_count"])
                claimed = [(i, f) for i, f in claimed if f]
                if claimed:
                    log("CONSUME", f"recovered pending messages={len(claimed)}")
                    return claimed
            resp = self.r.xreadgroup(self.group, self.name, {self.stream: ">"}, count=c["read_count"], block=c["block_ms"])
        except redis.exceptions.ResponseError as e:
            if "NOGROUP" in str(e):
                self._ensure_group()
                return []
            raise
        return [(i, f) for _s, entries in (resp or []) for i, f in entries]

    # ---- positions -------------------------------------------------------
    def reload(self, force=False):
        if not force and self.clock() - self._loaded_at < self.pm["positions_reload_seconds"]:
            return
        try:
            self.positions = store.list_open(self.db)
            self._loaded_at = self.clock()
        except Exception as e:  # noqa: BLE001
            log("LOAD", f"positions read failed: {type(e).__name__}: {e}", logging.ERROR, error_code=ERR_SYS_SQLITE)

    def symbols(self) -> set[str]:
        return {p["symbol"] for p in self.positions}

    # ---- stale -------------------------------------------------------------
    def ingest_state(self) -> tuple[bool, str | None]:
        st = self.pm["stale"]
        raw = self.r.get(st["ingest_health_key"])
        if not raw:
            return True, "ingestion heartbeat missing"
        beat = json.loads(raw)
        age = self.clock() - float(beat.get("epoch", 0))
        if age > st["ingest_max_age_seconds"]:
            return True, f"ingestion heartbeat age {age:.0f}s > {st['ingest_max_age_seconds']}s"
        if st.get("degraded_is_stale", True) and beat.get("mode") == "degraded":
            return True, "ingestion degraded"
        return False, None

    def stale_reason(self, q: dict | None, ingest: tuple[bool, str | None]) -> str | None:
        if q is None or q.get("price") is None:
            return "no quote"
        if q.get("stale"):
            return "quote flagged stale by ingestion"
        if q.get("ts") is None:
            return "quote timestamp invalid"
        age = self.clock() - q["ts"].timestamp()
        if age > self.pm["stale"]["max_quote_age_seconds"]:
            return f"quote age {age:.0f}s > {self.pm['stale']['max_quote_age_seconds']:.0f}s"
        if ingest[0]:
            return ingest[1]
        return None

    # ---- evaluate ------------------------------------------------------------
    def _track_price(self, symbol, q):
        if q.get("price") is None or q.get("ts") is None:
            return
        dq, win = self._prices[symbol], self.pm["volatility"]["window_seconds"]
        t = q["ts"].timestamp()
        if not dq or t > dq[-1][0]:
            dq.append((t, q["price"]))
        while dq and dq[-1][0] - dq[0][0] > win:
            dq.popleft()

    def evaluate_symbol(self, symbol: str, q: dict | None, ingest=None) -> list[dict]:
        ingest = ingest if ingest is not None else self.ingest_state()
        reason = self.stale_reason(q, ingest)
        if reason is None:
            self._track_price(symbol, q)
        out = []
        for p in [p for p in self.positions if p["symbol"] == symbol]:
            out.append(self.evaluate_position(p, q, reason))
        return out

    def evaluate_position(self, p: dict, q: dict | None, stale: str | None) -> dict:
        uid, sym, pid = str(p["user_id"]), p["symbol"], p["id"]
        t0 = time.monotonic()
        self.metrics["evaluations"] += 1
        state = {"position_id": pid, "user_id": uid, "symbol": sym, "quantity": p["quantity"], "entry_price": p["entry_price"],
                 "stop_loss": p["stop_loss"], "take_profit": p["take_profit"], "price": q.get("price") if q else None,
                 "quote_ts": q.get("timestamp") if q else None, "stale": stale is not None, "stale_reason": stale,
                 "pnl": None, "pnl_pct": None, "market_value": None, "alerts": [],
                 "updated_at": datetime.fromtimestamp(self.clock(), TZ).isoformat(timespec="seconds")}
        if state["price"] is not None:
            try:
                r = calc(p["entry_price"], p["quantity"], state["price"])
                state.update(pnl=r.pnl, pnl_pct=r.pnl_pct, market_value=r.market_value)
            except PnlError as e:
                self.metrics["pnl_errors"] += 1
                log("CALC", f"P&L error position={pid}: {e}", logging.ERROR, error_code=ERR_PNL, symbol=sym, user_id=uid, position_id=pid)
                state["error_code"] = ERR_PNL
        if stale is not None:
            self.metrics["stale_marks"] += 1
            key = f"{uid}:{sym}"
            if self.clock() - self._stale_logged.get(key, -1e18) >= self.pm["stale"]["log_every_seconds"]:
                self._stale_logged[key] = self.clock()
                log("STALE", f"price stale, alerts suppressed: {stale}", logging.WARNING, error_code=ERR_STALE,
                    symbol=sym, user_id=uid, position_id=pid)
        elif state["pnl"] is not None:
            state["alerts"] = self._thresholds(p, state)
        self._write_live(state)
        state["latency_ms"] = int((time.monotonic() - t0) * 1000)
        log("CALC", f"position={pid} price={state['price']} pnl={state['pnl']} pnl_pct={state['pnl_pct']} stale={state['stale']}",
            logging.DEBUG, symbol=sym, user_id=uid, latency_ms=state["latency_ms"], position_id=pid)
        return state

    def _thresholds(self, p, s) -> list[str]:
        fired, px = [], s["price"]
        if p["stop_loss"] is not None and px <= p["stop_loss"]:
            if self._fire_once(p, "sl", s, f"Chạm cắt lỗ {p['stop_loss']:,.0f} (giá {px:,.0f}, lãi/lỗ {s['pnl']:,.0f} VND / {s['pnl_pct']:.2f}%)"):
                fired.append("sl")
        if p["take_profit"] is not None and px >= p["take_profit"]:
            if self._fire_once(p, "tp", s, f"Chạm chốt lời {p['take_profit']:,.0f} (giá {px:,.0f}, lãi {s['pnl']:,.0f} VND / {s['pnl_pct']:.2f}%)"):
                fired.append("tp")
        v = self.pm["volatility"]
        dq = self._prices.get(p["symbol"])
        if v["enabled"] and dq and len(dq) >= 2 and dq[0][1] > 0:
            move = (px / dq[0][1] - 1) * 100
            if abs(move) >= v["threshold_pct"]:
                direction = "BUY" if move > 0 else "SELL"
                key = f"pos:vdedup:{p['id']}:{direction}"
                if self.r.set(key, 1, nx=True, ex=int(v["dedup_seconds"])):
                    span = dq[-1][0] - dq[0][0]
                    ok = self._publish(p, "vol", s, direction,
                                       f"Biến động bất thường {move:+.2f}% trong {span:.0f}s (từ {dq[0][1]:,.0f} -> {px:,.0f}); lãi/lỗ {s['pnl_pct']:.2f}%")
                    if ok:
                        fired.append("vol")
                    else:
                        self.r.delete(key)
                else:
                    log("DEDUP", f"volatility alert deduped position={p['id']} dir={direction}", symbol=p["symbol"],
                        user_id=str(p["user_id"]), position_id=p["id"])
        return fired

    def _fire_once(self, p, kind, s, reason) -> bool:
        if not store.mark_hit(self.db, p["id"], kind):
            log("DEDUP", f"{kind} already alerted position={p['id']}", logging.DEBUG, symbol=p["symbol"], user_id=str(p["user_id"]), position_id=p["id"])
            return False
        p[f"{kind}_hit_at"] = "now"
        if self._publish(p, kind, s, "SELL", reason):
            return True
        store.unmark_hit(self.db, p["id"], kind)
        return False

    def _publish(self, p, kind, s, direction, reason) -> bool:
        a = self.pm["alert"]
        sig = {"signal_id": "sig_pos" + uuid.uuid4().hex[:17], "user_id": str(p["user_id"]), "symbol": p["symbol"],
               "timestamp": datetime.fromtimestamp(self.clock(), TZ).isoformat(timespec="seconds"),
               "filter_name": a["filter_names"][kind], "direction": direction, "price": float(s["price"]),
               "reason": f"[Vị thế #{p['id']}] {reason}", "confidence": 1.0}
        try:
            entry = self.r.xadd(a["stream"], {k: str(v) for k, v in sig.items()}, maxlen=a["maxlen"], approximate=True)
        except Exception as e:  # noqa: BLE001
            log("ALERT", f"publish failed: {type(e).__name__}: {e}", logging.ERROR, error_code=ERR_SYS_REDIS,
                symbol=p["symbol"], user_id=str(p["user_id"]), position_id=p["id"])
            return False
        self.metrics["alerts"] += 1
        log("ALERT", f"published {kind} {direction} stream={a['stream']} id={entry}", symbol=p["symbol"], user_id=str(p["user_id"]),
            position_id=p["id"], signal_id=sig["signal_id"], filter_name=sig["filter_name"])
        return True

    def _write_live(self, s):
        lv = self.pm["live"]
        key = lv["key"].format(user_id=s["user_id"])
        try:
            pipe = self.r.pipeline()
            pipe.hset(key, str(s["position_id"]), json.dumps(s, ensure_ascii=False, default=str))
            pipe.expire(key, int(lv["ttl_seconds"]))
            pipe.execute()
        except Exception as e:  # noqa: BLE001
            log("LIVE", f"live state write failed: {e}", logging.ERROR, error_code=ERR_SYS_REDIS, symbol=s["symbol"], user_id=s["user_id"])

    # ---- vòng lặp -------------------------------------------------------------
    def sweep(self) -> list[dict]:
        self._last_sweep = self.clock()
        syms = sorted(self.symbols())
        if not syms:
            return []
        ingest = self.ingest_state()
        raws = self.r.mget([self.pm["quote_key"].format(symbol=s) for s in syms])
        out = []
        for sym, raw in zip(syms, raws):
            out += self.evaluate_symbol(sym, parse_quote(raw), ingest)
        return out

    def step(self) -> int:
        self.reload()
        batch = self._read()
        if batch:
            watched, latest = self.symbols(), {}
            for _i, f in batch:              # chỉ quote mới nhất mỗi mã đang có vị thế
                if f.get("symbol") in watched:
                    latest[f["symbol"]] = f
            if latest:
                ingest = self.ingest_state()
                for sym, f in latest.items():
                    try:
                        self.evaluate_symbol(sym, parse_quote(f), ingest)
                    except Exception as e:  # noqa: BLE001
                        self.metrics["errors"] += 1
                        log("EVAL", f"event failed: {type(e).__name__}: {e}", logging.ERROR, symbol=sym)
            self.r.xack(self.stream, self.group, *[i for i, _ in batch])
            self.metrics["events"] += len(batch)
        if self.clock() - self._last_sweep >= self.pm["sweep_seconds"]:
            self.sweep()
        return len(batch)

    def health(self) -> dict:
        stale_n = 0
        try:
            for uid in {str(p["user_id"]) for p in self.positions}:
                for v in self.r.hvals(self.pm["live"]["key"].format(user_id=uid)):
                    stale_n += bool(json.loads(v).get("stale"))
        except Exception:  # noqa: BLE001
            pass
        return {"ts": datetime.fromtimestamp(self.clock(), TZ).isoformat(timespec="seconds"), "epoch": self.clock(),
                "open_positions": len(self.positions), "symbols": sorted(self.symbols()), "stale_positions": stale_n,
                **self.metrics}

    def write_health(self) -> dict:
        beat = self.health()
        self.r.set(self.pm["health"]["key"], json.dumps(beat), ex=3600)
        return beat
