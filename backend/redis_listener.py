"""Subscribe to Redis Pub/Sub and fan-out ticks to WebSocket clients."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

from backend.observability import ERR_PB_REDIS, log, setup
from backend.volume_filter import load_min_volume, passes_volume_filter

if TYPE_CHECKING:
    from backend.websocket_manager import ConnectionManager

setup("redis")
COMPONENT = "redis"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
MIN_VOLUME = load_min_volume()


async def load_snapshot(redis: aioredis.Redis) -> list[dict]:
    """Load latest board state from Redis Hash for WS snapshot-on-connect."""
    raw = await redis.hgetall(HASH_KEY)
    rows: list[dict] = []
    for _symbol, payload in raw.items():
        try:
            row = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if passes_volume_filter(row, MIN_VOLUME):
            rows.append(row)
    rows.sort(key=lambda r: r.get("symbol", ""))
    return rows


class RedisTickListener:
    """Long-lived Pub/Sub listener; reconnects with backoff on failure."""

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="redis-tick-listener")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        delay = 1.0
        while not self._stop.is_set():
            try:
                await self._listen_loop()
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log(
                    COMPONENT,
                    "REDIS-LISTENER",
                    "pub/sub listener error",
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

    async def _listen_loop(self) -> None:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(CHANNEL)
            log(COMPONENT, "REDIS-SUB", "subscribed", channel=CHANNEL, hash=HASH_KEY)
            while not self._stop.is_set():
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message is None:
                    await asyncio.sleep(0.01)
                    continue
                data = message.get("data")
                if not data:
                    continue
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await self._manager.broadcast(data)
        finally:
            try:
                await pubsub.unsubscribe(CHANNEL)
                await pubsub.aclose()
            except Exception:
                pass
            await redis.aclose()
