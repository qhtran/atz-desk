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

from backend.observability import (
    ERR_PB_CONFIG,
    ERR_PB_PARSE,
    ERR_PB_REDIS_IO,
    ERR_PB_SSI_AUTH,
    ERR_PB_SSI_SESSION,
    PriceboardError,
    log,
    setup,
)
from backend.board_universe import INDEX_BOARD_SYMBOLS, default_watchlist, exchange_for_symbol
from backend.tick_contract import (
    build_tick,
    parse_ssi_envelope,
    ssi_envelope_has_symbol,
    tick_has_payload,
    tick_kind_for_symbol,
)
from backend.ssi_rest_bootstrap import (
    SsiRestClient,
    bootstrap_ticks,
    needs_rest_bootstrap,
)
from backend.volume_filter import load_volume_filter_settings, passes_volume_filter

setup("ssi_live")
COMPONENT = "ssi_live"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
VOLUME_FILTER = load_volume_filter_settings()

DEFAULT_WS = "wss://stream.ssi.com.vn/ws/v3"
DEFAULT_AUTH = "https://api.ssi.com.vn/api/v3/auth/token"

# Watchlist đa sàn khi config.symbols / ENV rỗng (VN30 + HOSE thêm + mẫu HNX/UPCOM)
DEFAULT_SYMBOLS = default_watchlist()

INDEX_SEED = [
    ("VNINDEX", 1285.4),
    ("VN30", 1342.1),
    ("VN30F1M", 1847.0),
    ("VN30F2M", 1850.2),
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
        log(
            COMPONENT,
            "CFG-YAML",
            "priceboard yaml unreadable",
            logging.WARNING,
            error_code=ERR_PB_CONFIG,
            exc=exc,
        )
        return {}


def _ssi_credentials() -> tuple[str, str]:
    cid = (os.getenv("SSI_CONSUMER_ID") or os.getenv("SSI_API_KEY") or "").strip()
    secret = (os.getenv("SSI_CONSUMER_SECRET") or os.getenv("SSI_API_SECRET") or "").strip()
    return cid, secret


def fetch_access_token(auth_url: str, api_key: str, api_secret: str, timeout: float = 20) -> str:
    try:
        r = requests.post(
            auth_url,
            json={"apiKey": api_key, "apiSecret": api_secret},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=timeout,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as exc:  # noqa: BLE001
        raise PriceboardError(ERR_PB_SSI_AUTH, "SSI token request failed", cause=exc) from exc
    tok = (
        body.get("accessToken")
        or body.get("access_token")
        or (body.get("data") or {}).get("accessToken")
        or (body.get("data") or {}).get("access_token")
    )
    if not tok:
        raise PriceboardError(
            ERR_PB_SSI_AUTH,
            f"SSI auth no token status={body.get('status')} msg={body.get('message')}",
        )
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
                "indexsummary.VN30F1M",
                "indexsummary.VN30F2M",
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
        self._parse_warn_at: float = 0.0

    def request_stop(self) -> None:
        self._stop.set()

    def _build_topics(self) -> list[str]:
        topics = list(self.index_topics)
        for sym in self.symbols:
            if sym in INDEX_BOARD_SYMBOLS:
                continue
            topics.append(f"quote.{sym}@tick")
            topics.append(f"quote.{sym}")
            topics.append(f"trade.{sym}@tick")
            topics.append(f"room.{sym}")
            topics.append(f"market.{sym}")
        # de-dupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    async def _load_board_from_redis(self, redis: aioredis.Redis) -> None:
        """Giữ snapshot phiên trước — không xóa hash khi reconnect WS."""
        raw = await redis.hgetall(HASH_KEY)
        loaded = 0
        for _sym, payload in raw.items():
            try:
                row = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                continue
            sym = str(row.get("symbol") or _sym).strip().upper()
            if sym:
                self._board[sym] = row
                loaded += 1
        log(COMPONENT, "SSI-LIVE-HYDRATE", "loaded redis board", rows=loaded)

    async def _bootstrap_rest(self, redis: aioredis.Redis, token: str) -> None:
        if (os.getenv("PRICEBOARD_REST_BOOTSTRAP") or "1").strip().lower() in ("0", "false", "no"):
            return
        data_base = (
            os.getenv("SSI_DATA_BASE_URL")
            or (dict(self._cfg.get("ssi") or {}).get("data_base_url"))
            or "https://api.ssi.com.vn/api/v3/data"
        )
        index_need = [s for s in INDEX_BOARD_SYMBOLS if needs_rest_bootstrap(self._board.get(s))]
        equity_need = [
            s
            for s in self.symbols
            if s not in INDEX_BOARD_SYMBOLS and needs_rest_bootstrap(self._board.get(s))
        ]
        if not index_need and not equity_need:
            return
        client = SsiRestClient(token, data_base=data_base)
        ticks = await asyncio.to_thread(
            bootstrap_ticks,
            client,
            index_symbols=index_need,
            equity_symbols=equity_need,
        )
        published = 0
        for tick in ticks:
            if not tick_has_payload(tick):
                continue
            await self._publish(redis, tick, merged=False)
            published += 1
        log(
            COMPONENT,
            "SSI-LIVE-REST-BOOT",
            "rest bootstrap applied",
            indexes=len(index_need),
            equities=len(equity_need),
            published=published,
        )

    _MERGE_KEYS = (
        "symbol",
        "kind",
        "last",
        "ref",
        "volume",
        "high",
        "low",
        "ceil",
        "floor",
        "change",
        "change_pct",
        "bid1",
        "bid2",
        "bid3",
        "bidVol1",
        "bidVol2",
        "bidVol3",
        "ask1",
        "ask2",
        "ask3",
        "askVol1",
        "askVol2",
        "askVol3",
        "matchVol",
        "foreignBuy",
        "foreignSell",
        "foreignBuyValue",
        "foreignSellValue",
    )

    def _partial_from_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        partial: dict[str, Any] = {"symbol": tick["symbol"]}
        for k in self._MERGE_KEYS:
            if k == "symbol":
                continue
            if k in tick and tick[k] is not None:
                partial[k] = tick[k]
        if "kind" not in partial and tick.get("kind"):
            partial["kind"] = tick["kind"]
        return partial

    async def _publish(self, redis: aioredis.Redis, tick: dict, *, merged: bool = False) -> None:
        if not merged:
            src = tick.get("source")
            extra = tick.get("extra")
            tick = self._merge_tick(self._partial_from_tick(tick))
            if src:
                tick["source"] = src
            if extra:
                tick["extra"] = extra
        sym = tick["symbol"]
        self._board[sym] = tick
        try:
            if not passes_volume_filter(tick, VOLUME_FILTER):
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
        exchange = exchange_for_symbol(sym)
        return build_tick(
            symbol=sym,
            last=last,
            ref=ref,
            kind=kind,
            exchange=exchange,
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
            foreignBuyValue=(
                parsed.get("foreignBuyValue")
                if parsed.get("foreignBuyValue") is not None
                else prev.get("foreignBuyValue")
            ),
            foreignSellValue=(
                parsed.get("foreignSellValue")
                if parsed.get("foreignSellValue") is not None
                else prev.get("foreignSellValue")
            ),
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
                code = ERR_PB_SSI_AUTH if isinstance(exc, PriceboardError) and exc.error_code == ERR_PB_SSI_AUTH else ERR_PB_SSI_SESSION
                log(
                    COMPONENT,
                    "SSI-LIVE-RECONNECT",
                    "ssi live session error",
                    logging.ERROR,
                    error_code=code,
                    exc=exc,
                    retry_in_s=delay,
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
            await self._load_board_from_redis(redis)
            await self._bootstrap_rest(redis, token)
            headers = {"Authorization": f"Bearer {token}"}
            log(
                COMPONENT,
                "SSI-LIVE-CONNECT",
                "connecting ssi websocket",
                ws_url=self.ws_url,
                channels=self.channels,
                topics=len(topics),
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
                log(COMPONENT, "SSI-LIVE-SUBSCRIBED", "ssi channels subscribed", channels=self.channels)

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
                        if ssi_envelope_has_symbol(msg):
                            now = time.time()
                            if now - self._parse_warn_at >= 60.0:
                                self._parse_warn_at = now
                                ch = str(msg.get("channel") or "")
                                body = msg.get("data") if isinstance(msg.get("data"), dict) else {}
                                log(
                                    COMPONENT,
                                    "SSI-PARSE-MISS",
                                    "ssi envelope had symbol but parse returned none",
                                    logging.WARNING,
                                    error_code=ERR_PB_PARSE,
                                    channel=ch,
                                    body_keys=sorted(body.keys()) if isinstance(body, dict) else [],
                                )
                        continue
                    tick = self._merge_tick(parsed)
                    if not tick_has_payload(tick):
                        continue
                    await self._publish(redis, tick, merged=True)
        finally:
            await redis.aclose()
            log(COMPONENT, "SSI-LIVE-SESSION-END", "ssi live session ended", t=int(time.time()))
