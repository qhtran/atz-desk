"""Mock SSI FastConnect worker for local / dev.atz.vn.

Publishes sample ticks to Redis Hash + Pub/Sub. Does NOT call SSI APIs.
Replace this module with a real FastConnect client in a later phase.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import signal
import time
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger("atz.priceboard.ssi_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
TICK_INTERVAL_MS = int(os.getenv("MOCK_TICK_INTERVAL_MS", "250"))
TZ_VN = timezone(timedelta(hours=7))

# Seed board — enough symbols for UI stress without flooding Redis.
SEED: list[dict] = [
    {"symbol": "VNINDEX", "exchange": "HOSE", "kind": "index", "ref": 1285.4, "last": 1285.4, "volume": 0},
    {"symbol": "VN30", "exchange": "HOSE", "kind": "index", "ref": 1342.1, "last": 1342.1, "volume": 0},
    {"symbol": "HNXINDEX", "exchange": "HNX", "kind": "index", "ref": 238.6, "last": 238.6, "volume": 0},
    {"symbol": "UPCOMINDEX", "exchange": "UPCOM", "kind": "index", "ref": 95.2, "last": 95.2, "volume": 0},
    {"symbol": "VNM", "exchange": "HOSE", "kind": "equity", "ref": 62500, "last": 62500, "volume": 1_250_000},
    {"symbol": "FPT", "exchange": "HOSE", "kind": "equity", "ref": 118500, "last": 118500, "volume": 980_000},
    {"symbol": "VCB", "exchange": "HOSE", "kind": "equity", "ref": 92500, "last": 92500, "volume": 2_100_000},
    {"symbol": "HPG", "exchange": "HOSE", "kind": "equity", "ref": 27800, "last": 27800, "volume": 8_400_000},
    {"symbol": "MWG", "exchange": "HOSE", "kind": "equity", "ref": 61200, "last": 61200, "volume": 1_800_000},
    {"symbol": "SSI", "exchange": "HOSE", "kind": "equity", "ref": 34200, "last": 34200, "volume": 5_200_000},
    {"symbol": "TCB", "exchange": "HOSE", "kind": "equity", "ref": 24500, "last": 24500, "volume": 3_600_000},
    {"symbol": "VIC", "exchange": "HOSE", "kind": "equity", "ref": 41500, "last": 41500, "volume": 2_900_000},
    {"symbol": "MSN", "exchange": "HOSE", "kind": "equity", "ref": 72800, "last": 72800, "volume": 1_100_000},
    {"symbol": "GAS", "exchange": "HOSE", "kind": "equity", "ref": 78500, "last": 78500, "volume": 450_000},
    {"symbol": "ACB", "exchange": "HOSE", "kind": "equity", "ref": 24850, "last": 24850, "volume": 4_200_000},
]


def _now_iso() -> str:
    return datetime.now(TZ_VN).isoformat()


def _tick_row(row: dict) -> dict:
    """Apply a small random move; equity ±1 tick-ish, index ± few points."""
    is_index = row["kind"] == "index"
    step = random.choice([-2, -1, 0, 0, 1, 2]) if is_index else random.choice(
        [-100, -50, 0, 0, 50, 100]
    )
    if is_index:
        last = round(float(row["last"]) + step * 0.1, 2)
        ceil = round(float(row["ref"]) * 1.07, 2)
        floor = round(float(row["ref"]) * 0.93, 2)
    else:
        last = int(row["last"]) + step
        ref = int(row["ref"])
        ceil = int(round(ref * 1.07 / 50) * 50)
        floor = int(round(ref * 0.93 / 50) * 50)
        last = max(floor, min(ceil, last))

    row["last"] = last
    row["high"] = max(float(row.get("high", last)), float(last))
    row["low"] = min(float(row.get("low", last)), float(last))
    if not is_index:
        row["volume"] = int(row.get("volume", 0)) + random.randint(0, 5_000)
        row["high"] = int(row["high"])
        row["low"] = int(row["low"])

    ref = float(row["ref"])
    change = float(last) - ref
    change_pct = (change / ref * 100.0) if ref else 0.0
    return {
        "type": "tick",
        "symbol": row["symbol"],
        "exchange": row["exchange"],
        "kind": row["kind"],
        "last": last,
        "ref": row["ref"],
        "change": round(change, 2) if is_index else int(change),
        "change_pct": round(change_pct, 2),
        "volume": int(row.get("volume", 0)),
        "high": row["high"],
        "low": row["low"],
        "ceil": ceil if is_index else int(ceil),
        "floor": floor if is_index else int(floor),
        "ts": _now_iso(),
        "source": "MOCK_SSI",
    }


class MockSsiWorker:
    """Reconnect-aware mock publisher (simulates SSI session lifecycle)."""

    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._state = [dict(r) for r in SEED]
        for row in self._state:
            row["high"] = row["last"]
            row["low"] = row["last"]

    def request_stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        delay = 1.0
        while not self._stop.is_set():
            try:
                await self._session()
                delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "DBG-PRICEBOARD-SSI-MOCK-RECONNECT err=%s retry_in=%.1fs",
                    exc,
                    delay,
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    return
                except asyncio.TimeoutError:
                    delay = min(delay * 2 + random.uniform(0, 0.5), 30.0)

    async def _session(self) -> None:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            # Seed hash so new WS clients get a non-empty snapshot.
            pipe = redis.pipeline()
            for row in self._state:
                payload = _tick_row(dict(row))
                # restore seed last without random walk on first write
                payload["last"] = row["last"]
                payload["change"] = 0
                payload["change_pct"] = 0.0
                payload["high"] = row["last"]
                payload["low"] = row["last"]
                pipe.hset(HASH_KEY, row["symbol"], json.dumps(payload, separators=(",", ":")))
            await pipe.execute()
            logger.info(
                "DBG-PRICEBOARD-SSI-MOCK-READY symbols=%s interval_ms=%s",
                len(self._state),
                TICK_INTERVAL_MS,
            )

            interval = max(TICK_INTERVAL_MS, 50) / 1000.0
            while not self._stop.is_set():
                row = random.choice(self._state)
                tick = _tick_row(row)
                # Keep in-memory state in sync with published last/vol.
                row["last"] = tick["last"]
                row["volume"] = tick["volume"]
                row["high"] = tick["high"]
                row["low"] = tick["low"]

                body = json.dumps(tick, ensure_ascii=False, separators=(",", ":"))
                await redis.hset(HASH_KEY, tick["symbol"], body)
                await redis.publish(CHANNEL, body)
                await asyncio.sleep(interval)
        finally:
            await redis.aclose()
            logger.info("DBG-PRICEBOARD-SSI-MOCK-SESSION-END t=%s", int(time.time()))


async def _amain() -> None:
    worker = MockSsiWorker()
    loop = asyncio.get_running_loop()

    def _handle_sig(*_args: object) -> None:
        logger.info("DBG-PRICEBOARD-SSI-MOCK-SIGNAL stopping")
        worker.request_stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            pass

    await worker.run()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
