"""Subscribe to Redis Pub/Sub and fan-out ticks to WebSocket clients."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

from backend.board_universe import INDEX_BOARD_SYMBOLS, INDEX_DEFAULT_REFS
from backend.observability import ERR_PB_REDIS, log, setup
from backend.tick_contract import build_tick
from backend.volume_filter import load_volume_filter_settings, passes_volume_filter

if TYPE_CHECKING:
    from backend.websocket_manager import ConnectionManager

setup("redis")
COMPONENT = "redis"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
VOLUME_FILTER = load_volume_filter_settings()


def merge_index_stubs(rows: list[dict]) -> list[dict]:
    """Đảm bảo snapshot WS có đủ INDEX_BOARD_SYMBOLS (stub nếu Redis thiếu)."""
    by_sym: dict[str, dict] = {}
    for row in rows:
        sym = str(row.get("symbol") or "").strip().upper()
        if sym:
            by_sym[sym] = row
    for sym in INDEX_BOARD_SYMBOLS:
        if sym in by_sym:
            continue
        ref = float(INDEX_DEFAULT_REFS.get(sym, 0.0))
        by_sym[sym] = build_tick(
            symbol=sym,
            last=ref,
            ref=ref,
            kind="index",
            volume=0,
            source="index_stub",
        )
    out = list(by_sym.values())
    out.sort(key=lambda r: str(r.get("symbol", "")))
    return out


async def load_snapshot(redis: aioredis.Redis) -> list[dict]:
    """Load latest board state from Redis Hash for WS snapshot-on-connect."""
    raw = await redis.hgetall(HASH_KEY)
    rows: list[dict] = []
    for _symbol, payload in raw.items():
        try:
            row = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            continue
        if passes_volume_filter(row, VOLUME_FILTER):
            rows.append(row)
    return merge_index_stubs(rows)


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
