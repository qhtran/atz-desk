"""Priceboard SSI worker — hybrid mock | live FastConnect.

PRICEBOARD_SOURCE=mock|ssi (default mock).
ssi mode requires SSI_CONSUMER_ID + SSI_CONSUMER_SECRET; otherwise falls back to mock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import signal
import time
from pathlib import Path
from typing import Any, Protocol

import redis.asyncio as aioredis

from backend.observability import ERR_PB_REDIS_IO, ERR_PB_SSI_FALLBACK, ERR_PB_SSI_SESSION, log, setup
from backend.tick_contract import build_tick
from backend.volume_filter import load_min_volume, passes_volume_filter

setup("worker")
COMPONENT = "worker"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
TICK_INTERVAL_MS = int(os.getenv("MOCK_TICK_INTERVAL_MS", "120"))
TICKS_PER_BURST = int(os.getenv("MOCK_TICKS_PER_BURST", "3"))
MOCK_EQUITY_COUNT = int(os.getenv("MOCK_EQUITY_COUNT", "70"))
MIN_VOLUME = load_min_volume()


async def _publish_or_hide(redis: aioredis.Redis, tick: dict) -> None:
    """Publish tick to hash+channel, or remove when equity fails volume gate."""
    sym = tick["symbol"]
    try:
        if not passes_volume_filter(tick, MIN_VOLUME):
            await redis.hdel(HASH_KEY, sym)
            remove = json.dumps(
                {"type": "remove", "symbol": sym},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            await redis.publish(CHANNEL, remove)
            return
        body = json.dumps(tick, ensure_ascii=False, separators=(",", ":"))
        await redis.hset(HASH_KEY, sym, body)
        await redis.publish(CHANNEL, body)
    except Exception as exc:  # noqa: BLE001
        log(
            COMPONENT,
            "REDIS-PUBLISH",
            "redis publish failed",
            logging.ERROR,
            error_code=ERR_PB_REDIS_IO,
            exc=exc,
            symbol=sym,
        )


VN30_AND_BLUECHIPS: list[tuple[str, int]] = [
    ("ACB", 24850), ("BCM", 68500), ("BID", 45200), ("BVH", 51200), ("CTG", 34500),
    ("FPT", 118500), ("GAS", 78500), ("GVR", 31200), ("HDB", 26800), ("HPG", 27800),
    ("LPB", 31200), ("MBB", 24500), ("MSN", 72800), ("MWG", 61200), ("PLX", 38500),
    ("SAB", 58200), ("SHB", 11200), ("SSB", 19800), ("SSI", 34200), ("STB", 35600),
    ("TCB", 24500), ("TPB", 17800), ("VCB", 92500), ("VHM", 41200), ("VIB", 19850),
    ("VIC", 41500), ("VJC", 98500), ("VNM", 62500), ("VPB", 19800), ("VRE", 18600),
    ("DGC", 92500), ("DIG", 18500), ("DXG", 15200), ("HCM", 28500), ("KDH", 31200),
    ("NLG", 34500), ("PNJ", 92500), ("POW", 12850), ("REE", 65200), ("TCH", 12500),
]


class Stoppable(Protocol):
    def request_stop(self) -> None: ...
    async def run(self) -> None: ...


def _load_yaml_source_default() -> str:
    path = Path(os.getenv("PRICEBOARD_CONFIG", "/app/config/priceboard.yaml"))
    if not path.is_file():
        alt = Path(__file__).resolve().parent.parent / "config" / "priceboard.yaml"
        path = alt if alt.is_file() else path
    if not path.is_file():
        return "mock"
    try:
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        src = ((doc.get("priceboard") or {}).get("source") or "mock")
        return str(src).strip().lower()
    except Exception:  # noqa: BLE001
        return "mock"


def resolve_source() -> str:
    """Return 'ssi' only when explicitly requested and credentials exist."""
    env = (os.getenv("PRICEBOARD_SOURCE") or "").strip().lower()
    src = env or _load_yaml_source_default() or "mock"
    if src != "ssi":
        return "mock"
    cid = (os.getenv("SSI_CONSUMER_ID") or os.getenv("SSI_API_KEY") or "").strip()
    secret = (os.getenv("SSI_CONSUMER_SECRET") or os.getenv("SSI_API_SECRET") or "").strip()
    if cid and secret:
        return "ssi"
    log(
        COMPONENT,
        "SOURCE-FALLBACK",
        "wanted ssi but missing SSI_CONSUMER_* — using mock",
        logging.WARNING,
        error_code=ERR_PB_SSI_FALLBACK,
    )
    return "mock"


def _synthetic_symbol(i: int) -> str:
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
    i = 0
    while len(seen) < target:
        sym = _synthetic_symbol(i)
        i += 1
        if sym in seen or len(sym) != 3:
            continue
        seen.add(sym)
        ref = 5_000 + (sum(ord(c) for c in sym) * 137) % 180_000
        ref = int(round(ref / 50) * 50)
        seed.append(_equity_row(sym, max(ref, 5_050)))
    return seed


def _tick_row(row: dict) -> dict:
    is_index = row["kind"] == "index"
    step = random.choice([-2, -1, 0, 0, 1, 2]) if is_index else random.choice(
        [-100, -50, 0, 0, 50, 100]
    )
    if is_index:
        last = round(float(row["last"]) + step * 0.1, 2)
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

    return build_tick(
        symbol=row["symbol"],
        last=row["last"],
        ref=row["ref"],
        kind=row["kind"],
        exchange=row.get("exchange", "HOSE"),
        volume=row.get("volume", 0),
        high=row.get("high"),
        low=row.get("low"),
        source="MOCK_SSI",
    )


class MockSsiWorker:
    """Reconnect-aware mock publisher (50–80 symbols for UI stress)."""

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
                log(
                    COMPONENT,
                    "SSI-MOCK-RECONNECT",
                    "mock worker session error",
                    logging.ERROR,
                    error_code=ERR_PB_SSI_SESSION,
                    exc=exc,
                    retry_in_s=delay,
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    return
                except asyncio.TimeoutError:
                    delay = min(delay * 2 + random.uniform(0, 0.5), 30.0)

    async def _session(self) -> None:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            await redis.delete(HASH_KEY)
            published = 0
            for row in self._state:
                payload = _tick_row(dict(row))
                payload["last"] = row["last"]
                payload["change"] = 0
                payload["change_pct"] = 0.0
                payload["high"] = row["last"]
                payload["low"] = row["last"]
                if passes_volume_filter(payload, MIN_VOLUME):
                    await redis.hset(
                        HASH_KEY,
                        row["symbol"],
                        json.dumps(payload, separators=(",", ":")),
                    )
                    published += 1
            n_eq = sum(1 for r in self._state if r["kind"] == "equity")
            log(
                COMPONENT,
                "SSI-MOCK-READY",
                "mock board ready",
                symbols=len(self._state),
                equities=n_eq,
                published=published,
                min_volume=MIN_VOLUME,
                interval_ms=TICK_INTERVAL_MS,
                burst=TICKS_PER_BURST,
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
                    await _publish_or_hide(redis, tick)
                await asyncio.sleep(interval)
        finally:
            await redis.aclose()
            log(COMPONENT, "SSI-MOCK-SESSION-END", "mock session ended", t=int(time.time()))


def create_worker() -> Stoppable:
    source = resolve_source()
    log(COMPONENT, "WORKER-BOOT", "ssi worker starting", source=source)
    if source == "ssi":
        from backend.ssi_live import RealSsiWorker

        return RealSsiWorker()
    return MockSsiWorker()


async def _amain() -> None:
    worker = create_worker()
    loop = asyncio.get_running_loop()

    def _handle_sig(*_args: object) -> None:
        log(COMPONENT, "WORKER-SIGNAL", "stop signal received")
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
