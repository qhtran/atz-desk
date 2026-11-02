"""Redis tick → vectorized quant alerts → WebSocket fan-out (Option B)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis
import yaml

from backend.engine.stream_evaluator import TickRingStore, evaluate_rings
from backend.observability import ERR_PB_REDIS, log, setup

if TYPE_CHECKING:
    from backend.websocket_manager import ConnectionManager

setup("stream")
COMPONENT = "stream"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DEFAULT_CFG = Path(
    os.getenv("STREAM_ALERTS_CONFIG", "config/stream_alerts.yaml")
)


def load_stream_alerts_config(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_CFG
    if not target.is_file():
        return {
            "enabled": True,
            "channel": os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks"),
            "evaluate_interval_ms": 2000,
            "cooldown_sec": 120,
            "ring_size": 80,
            "max_alerts_per_tick": 20,
            "rsi": {"length": 14, "oversold": 30, "overbought": 70},
            "ma": {"fast": 10, "slow": 20},
            "volume_spike": {"lookback": 20, "mult": 2.0},
            "risk_levels": {"high_below": 40, "low_above": 70},
        }
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


class QuantStreamListener:
    """Subscribe ticks (SSI live or mock); evaluate in thread pool; broadcast alerts."""

    def __init__(self, alert_manager: ConnectionManager, cfg: dict[str, Any] | None = None) -> None:
        self._alerts = alert_manager
        self._cfg = cfg or load_stream_alerts_config()
        self._store = TickRingStore(int(self._cfg.get("ring_size", 80)))
        self._task: asyncio.Task | None = None
        self._eval_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._dirty: set[str] = set()
        self._lock = asyncio.Lock()
        self._cooldown: dict[tuple[str, str], float] = {}

    def start(self) -> None:
        if not bool(self._cfg.get("enabled", True)):
            log(COMPONENT, "STREAM-OFF", "stream alerts disabled by config")
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_pubsub(), name="quant-stream-pubsub")
        self._eval_task = asyncio.create_task(self._run_evaluator(), name="quant-stream-eval")
        log(
            COMPONENT,
            "STREAM-START",
            "quant stream listener started",
            channel=self._cfg.get("channel"),
            interval_ms=self._cfg.get("evaluate_interval_ms"),
        )

    async def stop(self) -> None:
        self._stop.set()
        for task in (self._task, self._eval_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._eval_task = None

    async def _run_pubsub(self) -> None:
        channel = str(self._cfg.get("channel") or os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks"))
        delay = 1.0
        while not self._stop.is_set():
            try:
                await self._listen_loop(channel)
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log(
                    COMPONENT,
                    "STREAM-SUB",
                    "stream pub/sub error",
                    logging.ERROR,
                    error_code=ERR_PB_REDIS,
                    exc=exc,
                    retry_in_s=delay,
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    return
                except asyncio.TimeoutError:
                    delay = min(delay * 2, 30.0)

    async def _listen_loop(self, channel: str) -> None:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(channel)
            while not self._stop.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.01)
                    continue
                data = message.get("data")
                if not data:
                    continue
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                self._ingest_payload(data)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass
            await redis.aclose()

    def _ingest_payload(self, data: str) -> None:
        try:
            payload = json.loads(data)
        except (TypeError, json.JSONDecodeError):
            return
        rows: list[dict[str, Any]]
        if isinstance(payload, dict) and payload.get("type") == "snapshot":
            rows = list(payload.get("rows") or [])
        elif isinstance(payload, dict) and payload.get("symbol"):
            rows = [payload]
        elif isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)]
        else:
            return
        for row in rows:
            sym = str(row.get("symbol") or "").upper()
            if not sym:
                continue
            last = row.get("last")
            if last is None:
                last = row.get("close")
            vol = row.get("volume")
            if vol is None:
                vol = row.get("matchVol") or row.get("match_vol")
            self._store.update(sym, last, vol)
            self._dirty.add(sym)

    async def _run_evaluator(self) -> None:
        interval = max(0.5, float(self._cfg.get("evaluate_interval_ms", 2000)) / 1000.0)
        while not self._stop.is_set():
            try:
                await asyncio.sleep(interval)
                async with self._lock:
                    dirty = set(self._dirty)
                    self._dirty.clear()
                if not dirty and not self._store.symbols():
                    continue
                alerts = await asyncio.to_thread(evaluate_rings, self._store, self._cfg)
                now = time.time()
                cooldown = float(self._cfg.get("cooldown_sec", 120))
                for alert in alerts:
                    key = (alert.symbol, alert.indicator)
                    last = self._cooldown.get(key, 0.0)
                    if now - last < cooldown:
                        continue
                    self._cooldown[key] = now
                    await self._alerts.broadcast_json(alert.to_dict())
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log(
                    COMPONENT,
                    "STREAM-EVAL",
                    "stream evaluate error",
                    logging.WARNING,
                    error_code=ERR_PB_REDIS,
                    exc=exc,
                )
