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
TICK_INTERVAL_MS = int(os.getenv("MOCK_TICK_INTERVAL_MS", "120"))
TICKS_PER_BURST = int(os.getenv("MOCK_TICKS_PER_BURST", "3"))
MOCK_EQUITY_COUNT = int(os.getenv("MOCK_EQUITY_COUNT", "70"))  # target equities (50–80)
TZ_VN = timezone(timedelta(hours=7))

# VN30 + common HOSE names (approx basket for UI realism).
VN30_AND_BLUECHIPS: list[tuple[str, int]] = [
    ("ACB", 24850), ("BCM", 68500), ("BID", 45200), ("BVH", 51200), ("CTG", 34500),
    ("FPT", 118500), ("GAS", 78500), ("GVR", 31200), ("HDB", 26800), ("HPG", 27800),
    ("LPB", 31200), ("MBB", 24500), ("MSN", 72800), ("MWG", 61200), ("PLX", 38500),
    ("SAB", 58200), ("SHB", 11200), ("SSB", 19800), ("SSI", 34200), ("STB", 35600),
    ("TCB", 24500), ("TPB", 17800), ("VCB", 92500), ("VHM", 41200), ("VIB", 19850),
    ("VIC", 41500), ("VJC", 98500), ("VNM", 62500), ("VPB", 19800), ("VRE", 18600),
    # extra liquid names beyond VN30
    ("DGC", 92500), ("DIG", 18500), ("DXG", 15200), ("HCM", 28500), ("KDH", 31200),
    ("NLG", 34500), ("PNJ", 92500), ("POW", 12850), ("REE", 65200), ("TCH", 12500),
]


def _synthetic_symbol(i: int) -> str:
    """AAA, AAB, AAC … then BAA, BAB … (base-26 style, A–Z)."""
    n = i
    chars = []
    for _ in range(3):
        chars.append(chr(ord("A") + (n % 26)))
        n //= 26
    return "".join(reversed(chars))


def _equity_row(symbol: str, ref: int, exchange: str = "HOSE") -> dict:
    return {
        "symbol": symbol,
        "exchange": exchange,
        "kind": "equity",
        "ref": ref,
        "last": ref,
        "volume": random.randint(50_000, 9_000_000),
    }


def build_seed(equity_count: int | None = None) -> list[dict]:
    """Build index + 50–80 equities for scroll / sticky header stress tests."""
    target = equity_count if equity_count is not None else MOCK_EQUITY_COUNT
    target = max(50, min(80, target))

    seed: list[dict] = [
        {"symbol": "VNINDEX", "exchange": "HOSE", "kind": "index", "ref": 1285.4, "last": 1285.4, "volume": 0},
        {"symbol": "VN30", "exchange": "HOSE", "kind": "index", "ref": 1342.1, "last": 1342.1, "volume": 0},
        {"symbol": "HNXINDEX", "exchange": "HNX", "kind": "index", "ref": 238.6, "last": 238.6, "volume": 0},
        {"symbol": "UPCOMINDEX", "exchange": "UPCOM", "kind": "index", "ref": 95.2, "last": 95.2, "volume": 0},
    ]

    seen: set[str] = set()
    for sym, ref in VN30_AND_BLUECHIPS:
        if len(seen) >= target:
            break
        if sym in seen:
            continue
        seen.add(sym)
        seed.append(_equity_row(sym, ref))

    # Fill remaining with synthetic tickers AAA, AAB, …
    i = 0
    while len(seen) < target:
        sym = _synthetic_symbol(i)
        i += 1
        if sym in seen or len(sym) != 3:
            continue
        seen.add(sym)
        # Deterministic-ish price from symbol hash
        ref = 5_000 + (sum(ord(c) for c in sym) * 137) % 180_000
        ref = int(round(ref / 50) * 50)
        seed.append(_equity_row(sym, max(ref, 5_050)))

    return seed


SEED: list[dict] = build_seed()


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
        self._state = [dict(r) for r in build_seed()]
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
            # Reset hash so removed symbols from older seeds do not linger.
            await redis.delete(HASH_KEY)
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
            n_eq = sum(1 for r in self._state if r["kind"] == "equity")
            logger.info(
                "DBG-PRICEBOARD-SSI-MOCK-READY symbols=%s equities=%s interval_ms=%s burst=%s",
                len(self._state),
                n_eq,
                TICK_INTERVAL_MS,
                TICKS_PER_BURST,
            )

            interval = max(TICK_INTERVAL_MS, 50) / 1000.0
            burst = max(1, TICKS_PER_BURST)
            while not self._stop.is_set():
                picks = random.sample(self._state, k=min(burst, len(self._state)))
                for row in picks:
                    tick = _tick_row(row)
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
