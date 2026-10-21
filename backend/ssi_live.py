"""Live SSI FastConnect WebSocket → Redis Hash + Pub/Sub (priceboard contract).

Uses ENV credentials only (SSI_CONSUMER_ID / SSI_CONSUMER_SECRET).
Subscribes DATA + X-Quote + X-Trade + MI; maps payloads via tick_contract.
Does NOT write idx:quote:* (avoids dual-writer with atz-ssi-stream).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
import requests
import websockets
from websockets.exceptions import ConnectionClosed

from backend.tick_contract import build_tick, parse_ssi_envelope
from backend.volume_filter import load_min_volume, passes_volume_filter

logger = logging.getLogger("atz.priceboard.ssi_live")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
MIN_VOLUME = load_min_volume()

DEFAULT_WS = "wss://stream.ssi.com.vn/ws/v3"
DEFAULT_AUTH = "https://api.ssi.com.vn/api/v3/auth/token"

# VN30-ish watchlist when config.symbols empty
DEFAULT_SYMBOLS = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "LPB", "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
]

INDEX_SEED = [
    ("VNINDEX", 1285.4),
    ("VN30", 1342.1),
    ("HNXINDEX", 238.6),
    ("UPCOMINDEX", 95.2),
]


def _load_yaml_cfg() -> dict[str, Any]:
    path = Path(os.getenv("PRICEBOARD_CONFIG", "/app/config/priceboard.yaml"))
    if not path.is_file():
        # repo-relative when running outside Docker
        alt = Path(__file__).resolve().parent.parent / "config" / "priceboard.yaml"
        path = alt if alt.is_file() else path
    if not path.is_file():
        return {}
    try:
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return dict(doc.get("priceboard") or {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("DBG-PRICEBOARD-CFG-YAML-ERR err=%s", exc)
        return {}


def _ssi_credentials() -> tuple[str, str]:
    cid = (os.getenv("SSI_CONSUMER_ID") or os.getenv("SSI_API_KEY") or "").strip()
    secret = (os.getenv("SSI_CONSUMER_SECRET") or os.getenv("SSI_API_SECRET") or "").strip()
    return cid, secret


def fetch_access_token(auth_url: str, api_key: str, api_secret: str, timeout: float = 20) -> str:
    r = requests.post(
        auth_url,
        json={"apiKey": api_key, "apiSecret": api_secret},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    tok = (
        body.get("accessToken")
        or body.get("access_token")
        or (body.get("data") or {}).get("accessToken")
        or (body.get("data") or {}).get("access_token")
    )
    if not tok:
        raise RuntimeError(f"SSI auth no token status={body.get('status')} msg={body.get('message')}")
    return str(tok)


class RealSsiWorker:
    """Async SSI WS → priceboard Redis. Reconnect with exponential backoff."""

    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._cfg = _load_yaml_cfg()
        ssi = dict(self._cfg.get("ssi") or {})
        self.ws_url = os.getenv("SSI_WS_URL") or ssi.get("ws_url") or DEFAULT_WS
        self.auth_url = os.getenv("SSI_AUTH_URL") or ssi.get("auth_url") or DEFAULT_AUTH
        self.channels = [
            c.strip()
            for c in (
                os.getenv("PRICEBOARD_SSI_CHANNELS")
                or ",".join(ssi.get("channels") or ["DATA", "X-Quote", "X-Trade", "MI"])
            ).split(",")
            if c.strip()
        ]
        self.index_topics = list(
            ssi.get("index_topics")
            or [
                "indexsummary.VNINDEX",
                "indexsummary.VN30",
                "indexsummary.HNXINDEX",
                "indexsummary.UPCOMINDEX",
            ]
        )
        cfg_syms = [str(s).upper() for s in (ssi.get("symbols") or []) if s]
        env_syms = [
            s.strip().upper()
            for s in (os.getenv("PRICEBOARD_SYMBOLS") or "").split(",")
            if s.strip()
        ]
        self.symbols = env_syms or cfg_syms or list(DEFAULT_SYMBOLS)
        self.reconnect_initial = float(
            os.getenv("SSI_RECONNECT_INITIAL") or ssi.get("reconnect_initial_seconds") or 2
        )
        self.reconnect_max = float(
            os.getenv("SSI_RECONNECT_MAX") or ssi.get("reconnect_max_seconds") or 60
        )
        self._board: dict[str, dict] = {}

    def request_stop(self) -> None:
        self._stop.set()

    def _build_topics(self) -> list[str]:
        topics = list(self.index_topics)
        for sym in self.symbols:
            topics.append(f"quote.{sym}@tick")
            topics.append(f"trade.{sym}@tick")
        # de-dupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    async def _seed_skeleton(self, redis: aioredis.Redis) -> None:
        await redis.delete(HASH_KEY)
        pipe = redis.pipeline()
        for sym, ref in INDEX_SEED:
            tick = build_tick(
                symbol=sym,
                last=ref,
                ref=ref,
                kind="index",
                volume=0,
                source="SSI_WS",
            )
            self._board[sym] = tick
            pipe.hset(HASH_KEY, sym, json.dumps(tick, separators=(",", ":")))
        for sym in self.symbols:
            tick = build_tick(
                symbol=sym,
                last=0,
                ref=0,
                kind="equity",
                volume=0,
                source="SSI_WS",
            )
            # last=0 looks empty — keep row shell; FE still shows until first tick
            self._board[sym] = tick
            pipe.hset(HASH_KEY, sym, json.dumps(tick, separators=(",", ":")))
        await pipe.execute()
        logger.info(
            "DBG-PRICEBOARD-SSI-LIVE-SEED indexes=%s equities=%s min_volume=%s",
            len(INDEX_SEED),
            len(self.symbols),
            MIN_VOLUME,
        )

    async def _publish(self, redis: aioredis.Redis, tick: dict) -> None:
        sym = tick["symbol"]
        self._board[sym] = tick
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

    @staticmethod
    def _merge_extreme(
        incoming: Any,
        prev: Any,
        last: Any,
        kind: str,
        *,
        which: str,
    ) -> Any:
        """Session high/low. Index summary rarely sends h/l — track from last."""
        if incoming is not None:
            return incoming
        if kind != "index":
            return prev
        try:
            last_f = float(last)
        except (TypeError, ValueError):
            return prev
        try:
            prev_f = float(prev) if prev is not None else None
        except (TypeError, ValueError):
            prev_f = None
        # Ignore seed extremes far from live last (e.g. hardcoded INDEX_SEED)
        if prev_f is None or prev_f <= 0 or abs(prev_f - last_f) / max(abs(last_f), 1.0) > 0.2:
            return last_f
        if which == "high":
            return max(prev_f, last_f)
        return min(prev_f, last_f)

    def _merge_tick(self, parsed: dict[str, Any]) -> dict[str, Any]:
        sym = parsed["symbol"]
        prev = self._board.get(sym) or {}
        kind = parsed.get("kind") or prev.get("kind") or "equity"
        last = parsed.get("last")
        if last is None:
            last = prev.get("last") or 0
        ref = parsed.get("ref")
        if ref is None:
            ref = prev.get("ref") or last
        # Index SSI không gửi trần/sàn giá (ce/fl = đếm mã) — luôn tính lại từ ref.
        if parsed.get("ceil") is not None:
            ceil = parsed.get("ceil")
        elif kind == "index":
            ceil = None
        else:
            ceil = prev.get("ceil")
        if parsed.get("floor") is not None:
            floor = parsed.get("floor")
        elif kind == "index":
            floor = None
        else:
            floor = prev.get("floor")
        return build_tick(
            symbol=sym,
            last=last,
            ref=ref,
            kind=kind,
            volume=parsed.get("volume") if parsed.get("volume") is not None else prev.get("volume", 0),
            high=self._merge_extreme(parsed.get("high"), prev.get("high"), last, kind, which="high"),
            low=self._merge_extreme(parsed.get("low"), prev.get("low"), last, kind, which="low"),
            ceil=ceil,
            floor=floor,
            change=parsed.get("change"),
            change_pct=parsed.get("change_pct"),
            bid1=parsed.get("bid1") if parsed.get("bid1") is not None else prev.get("bid1"),
            bid2=parsed.get("bid2") if parsed.get("bid2") is not None else prev.get("bid2"),
            bid3=parsed.get("bid3") if parsed.get("bid3") is not None else prev.get("bid3"),
            bidVol1=parsed.get("bidVol1") if parsed.get("bidVol1") is not None else prev.get("bidVol1"),
            bidVol2=parsed.get("bidVol2") if parsed.get("bidVol2") is not None else prev.get("bidVol2"),
            bidVol3=parsed.get("bidVol3") if parsed.get("bidVol3") is not None else prev.get("bidVol3"),
            ask1=parsed.get("ask1") if parsed.get("ask1") is not None else prev.get("ask1"),
            ask2=parsed.get("ask2") if parsed.get("ask2") is not None else prev.get("ask2"),
            ask3=parsed.get("ask3") if parsed.get("ask3") is not None else prev.get("ask3"),
            askVol1=parsed.get("askVol1") if parsed.get("askVol1") is not None else prev.get("askVol1"),
            askVol2=parsed.get("askVol2") if parsed.get("askVol2") is not None else prev.get("askVol2"),
            askVol3=parsed.get("askVol3") if parsed.get("askVol3") is not None else prev.get("askVol3"),
            matchVol=parsed.get("matchVol") if parsed.get("matchVol") is not None else prev.get("matchVol"),
            foreignBuy=parsed.get("foreignBuy") if parsed.get("foreignBuy") is not None else prev.get("foreignBuy"),
            foreignSell=parsed.get("foreignSell") if parsed.get("foreignSell") is not None else prev.get("foreignSell"),
            source="SSI_WS",
            extra={"ssi_channel": parsed.get("channel") or ""},
        )

    async def run(self) -> None:
        delay = self.reconnect_initial
        while not self._stop.is_set():
            try:
                await self._session()
                delay = self.reconnect_initial
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "DBG-PRICEBOARD-SSI-LIVE-RECONNECT err=%s retry_in=%.1fs",
                    exc,
                    delay,
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                    return
                except asyncio.TimeoutError:
                    delay = min(delay * 2 + random.uniform(0, 0.5), self.reconnect_max)

    async def _session(self) -> None:
        api_key, api_secret = _ssi_credentials()
        if not api_key or not api_secret:
            raise RuntimeError("missing SSI_CONSUMER_ID / SSI_CONSUMER_SECRET")

        token = await asyncio.to_thread(fetch_access_token, self.auth_url, api_key, api_secret)
        topics = self._build_topics()
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            await self._seed_skeleton(redis)
            headers = {"Authorization": f"Bearer {token}"}
            logger.info(
                "DBG-PRICEBOARD-SSI-LIVE-CONNECT url=%s channels=%s topics=%s",
                self.ws_url,
                self.channels,
                len(topics),
            )
            async with websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=None,
                max_size=8 * 1024 * 1024,
            ) as ws:
                for ch in self.channels:
                    sub = {"method": "SUBSCRIBE", "channel": ch, "topics": topics}
                    await ws.send(json.dumps(sub))
                logger.info("DBG-PRICEBOARD-SSI-LIVE-SUBSCRIBED channels=%s", self.channels)

                while not self._stop.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    except asyncio.TimeoutError:
                        # keep-alive probe
                        try:
                            await ws.send(json.dumps({"method": "PONG", "channel": "HEARTBEAT", "time": time.strftime("%d-%m-%Y %H-%M-%S")}))
                        except Exception:  # noqa: BLE001
                            raise ConnectionClosed(None, None)
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(msg, dict):
                        continue

                    method = str(msg.get("method") or "").upper()
                    channel = str(msg.get("channel") or "").upper()
                    if method == "PING" or (channel == "HEARTBEAT" and method != "PONG"):
                        await ws.send(
                            json.dumps(
                                {
                                    "method": "PONG",
                                    "channel": "HEARTBEAT",
                                    "time": msg.get("time") or time.strftime("%d-%m-%Y %H-%M-%S"),
                                }
                            )
                        )
                        continue

                    parsed = parse_ssi_envelope(msg)
                    if not parsed:
                        continue
                    tick = self._merge_tick(parsed)
                    if tick["kind"] == "equity" and float(tick.get("last") or 0) == 0 and float(tick.get("ref") or 0) == 0:
                        continue
                    await self._publish(redis, tick)
        finally:
            await redis.aclose()
            logger.info("DBG-PRICEBOARD-SSI-LIVE-SESSION-END t=%s", int(time.time()))
