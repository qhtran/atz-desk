#!/usr/bin/env python3
"""Mock market ticks → Redis Pub/Sub (Option B / ngoài giờ GD).

Bơm tick vào channel ``priceboard_ticks`` (+ hash ``priceboard:quotes``) để
``QuantStreamListener`` / SPA ``/ws/stream/alerts`` có dữ liệu khi SSI đóng cửa.

Chạy từ root repo (Mac hoặc VPS):

    # Redis desk-dev map host :6380
    REDIS_URL=redis://127.0.0.1:6380/0 python3 scripts/mock_tick_generator.py

    # Trong mạng Docker (service redis):
    REDIS_URL=redis://redis:6379/0 python3 scripts/mock_tick_generator.py

Ctrl+C để dừng.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import redis.asyncio as aioredis

from backend.tick_contract import build_tick, slim_ws_tick

DEFAULT_SYMBOLS: dict[str, dict[str, float | str]] = {
    "SSI": {"ref": 28000, "exchange": "HOSE"},
    "VHM": {"ref": 42000, "exchange": "HOSE"},
    "FPT": {"ref": 95000, "exchange": "HOSE"},
    "HPG": {"ref": 27000, "exchange": "HOSE"},
    "MWG": {"ref": 45000, "exchange": "HOSE"},
    "TCB": {"ref": 24000, "exchange": "HOSE"},
    "VCB": {"ref": 92000, "exchange": "HOSE"},
    "VNM": {"ref": 68000, "exchange": "HOSE"},
    "MSN": {"ref": 75000, "exchange": "HOSE"},
    "ACB": {"ref": 25000, "exchange": "HOSE"},
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mock tick publisher for priceboard_ticks")
    p.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        help="Redis URL (default REDIS_URL or redis://127.0.0.1:6379/0)",
    )
    p.add_argument(
        "--channel",
        default=os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks"),
    )
    p.add_argument(
        "--hash",
        default=os.getenv("PRICEBOARD_HASH", "priceboard:quotes"),
    )
    p.add_argument("--min-sleep", type=float, default=0.2)
    p.add_argument("--max-sleep", type=float, default=0.5)
    p.add_argument(
        "--seed-trend",
        choices=("random", "down", "up"),
        default="down",
        help="down = dễ kích RSI_OVERSOLD cho smoke Option B",
    )
    return p.parse_args()


def _step_price(last: float, ref: float, mode: str) -> float:
    if mode == "down":
        pct = random.uniform(-0.012, -0.001)
    elif mode == "up":
        pct = random.uniform(0.001, 0.012)
    else:
        pct = random.uniform(-0.01, 0.01)
    nxt = last * (1.0 + pct)
    lo, hi = ref * 0.93, ref * 1.07
    return max(lo, min(hi, nxt))


async def _publish(redis: aioredis.Redis, channel: str, hash_key: str, tick: dict) -> None:
    full = json.dumps(tick, ensure_ascii=False, separators=(",", ":"))
    slim = json.dumps(slim_ws_tick(tick), ensure_ascii=False, separators=(",", ":"))
    await redis.hset(hash_key, tick["symbol"], full)
    await redis.publish(channel, slim)


async def run(args: argparse.Namespace) -> None:
    state: dict[str, dict] = {}
    for sym, meta in DEFAULT_SYMBOLS.items():
        ref = float(meta["ref"])
        state[sym] = {
            "ref": ref,
            "last": ref,
            "high": ref,
            "low": ref,
            "volume": random.randint(50_000, 200_000),
            "exchange": str(meta["exchange"]),
        }

    redis = aioredis.from_url(args.redis_url, decode_responses=True)
    print(
        f"[mock-tick] redis={args.redis_url} channel={args.channel} "
        f"hash={args.hash} symbols={len(state)} trend={args.seed_trend}",
        flush=True,
    )
    try:
        await redis.ping()
    except Exception as exc:
        print(f"[mock-tick] Redis ping FAIL: {exc}", file=sys.stderr)
        await redis.aclose()
        raise SystemExit(1) from exc

    n = 0
    try:
        while True:
            sym = random.choice(list(state.keys()))
            row = state[sym]
            last = _step_price(float(row["last"]), float(row["ref"]), args.seed_trend)
            row["last"] = last
            row["high"] = max(float(row["high"]), last)
            row["low"] = min(float(row["low"]), last)
            row["volume"] = int(row["volume"]) + random.randint(1_000, 80_000)
            vol = int(row["volume"])
            if random.random() < 0.08:
                vol = int(vol * random.uniform(2.5, 4.0))
                row["volume"] = vol

            tick = build_tick(
                symbol=sym,
                last=last,
                ref=row["ref"],
                kind="equity",
                exchange=row["exchange"],
                volume=vol,
                high=row["high"],
                low=row["low"],
                source="MOCK_GEN",
            )
            await _publish(redis, args.channel, args.hash, tick)
            n += 1
            if n % 50 == 0:
                print(
                    f"[mock-tick] published={n} last={sym}@{tick['last']} ts={int(time.time())}",
                    flush=True,
                )
            await asyncio.sleep(random.uniform(args.min_sleep, args.max_sleep))
    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        print(f"[mock-tick] stop after {n} ticks", flush=True)
    finally:
        await redis.aclose()


def main() -> None:
    args = _parse_args()
    if args.min_sleep > args.max_sleep:
        args.min_sleep, args.max_sleep = args.max_sleep, args.min_sleep
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
