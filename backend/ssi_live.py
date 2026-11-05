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
from backend.board_universe import (
    FUTURES_BOARD_SYMBOLS,
    INDEX_BOARD_SYMBOLS,
    default_watchlist,
    exchange_for_symbol,
)
from backend.market_catalog import load_core_symbol_set
from backend.futures_contracts import invert_contract_map, load_futures_contract_map
from backend.tick_contract import (
    build_tick,
    slim_ws_tick,
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
from backend.equity_spark import record_equity_spark
from backend.index_spark import record_index_spark
from backend.ondemand_watch import ONDEMAND_HASH, ONDEMAND_IDLE_SEC
from backend.volume_filter import load_volume_filter_settings, passes_volume_filter

setup("ssi_live")
COMPONENT = "ssi_live"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")
HASH_KEY = os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
VOLUME_FILTER = load_volume_filter_settings()


def reload_volume_filter() -> None:
    """Hot-reload volume gate from Admin-First overlay (never raises)."""
    global VOLUME_FILTER  # noqa: PLW0603
    try:
        VOLUME_FILTER = load_volume_filter_settings()
    except Exception:
        pass

DEFAULT_WS = "wss://stream.ssi.com.vn/ws/v3"
DEFAULT_AUTH = "https://api.ssi.com.vn/api/v3/auth/token"

def _default_core_symbols() -> list[str]:
    """Prefer Top-N core YAML; fallback board_universe.default_watchlist()."""
    try:
        core = sorted(load_core_symbol_set())
        if core:
            return core
    except Exception:
        pass
    return list(default_watchlist())


# Core stream when config.symbols / ENV rỗng
DEFAULT_SYMBOLS = _default_core_symbols()

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
        self.symbols = env_syms or cfg_syms or _default_core_symbols()
        self.reconnect_initial = float(
            os.getenv("SSI_RECONNECT_INITIAL") or ssi.get("reconnect_initial_seconds") or 2
        )
        self.reconnect_max = float(
            os.getenv("SSI_RECONNECT_MAX") or ssi.get("reconnect_max_seconds") or 60
        )
        self._board: dict[str, dict] = {}
        self._parse_warn_at: float = 0.0
        self._futures_sample_at: float = 0.0
        self._ondemand_active: set[str] = set()
        self._ondemand_idle_sec = float(
            os.getenv("PRICEBOARD_ONDEMAND_IDLE_SEC") or ONDEMAND_IDLE_SEC
        )
        self._futures_contracts = load_futures_contract_map(ssi)
        self._contract_to_board = invert_contract_map(self._futures_contracts)
        self._pending_ops_reload = False
        self._ondemand_sync_enabled = True
        self._maintenance_mode = False
        if self._futures_contracts:
            log(
                COMPONENT,
                "SSI-FUTURES-MAP",
                "HĐTL board→contract",
                contracts=self._futures_contracts,
            )
        self._load_ops_flags()

    def _load_ops_flags(self) -> None:
        try:
            from backend.admin_config_store import _read_overlay
            from backend.ops_config import effective_priceboard_ops

            ops = effective_priceboard_ops(_read_overlay())
            self._ondemand_sync_enabled = bool(ops.get("ondemand_sync_enabled", True))
            self._maintenance_mode = bool(ops.get("maintenance_mode", False))
        except Exception:
            self._ondemand_sync_enabled = True
            self._maintenance_mode = False

    def request_ops_reload(self) -> None:
        """Mark pending Admin-First config reload (applied on WS loop)."""
        self._pending_ops_reload = True

    def request_stop(self) -> None:
        self._stop.set()

    def _remap_futures_symbol(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """X-Quote dùng mã HĐ (41I1…) → ghi board VN30F1M/F2M."""
        sym = str(parsed.get("symbol") or "").strip().upper()
        board = self._contract_to_board.get(sym)
        if not board:
            return parsed
        out = dict(parsed)
        out["symbol"] = board
        out["kind"] = "equity"
        out["contract"] = sym
        return out

    def _equity_like_symbols(self) -> list[str]:
        """Mã depth: cổ phiếu + mã HĐ SSI (không dùng VN30F* cho X-Quote)."""
        out: list[str] = []
        seen: set[str] = set()
        for sym in self.symbols:
            s = str(sym or "").strip().upper()
            if not s or s in seen or s in INDEX_BOARD_SYMBOLS:
                continue
            seen.add(s)
            out.append(s)
        for board in FUTURES_BOARD_SYMBOLS:
            code = self._futures_contracts.get(board) or board
            c = str(code).strip().upper()
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _append_quote_topics(self, topics: list[str], sym: str) -> None:
        topics.append(f"quote.{sym}@tick")
        topics.append(f"quote.{sym}")
        topics.append(f"trade.{sym}@tick")
        topics.append(f"room.{sym}")
        topics.append(f"market.{sym}")

    def _all_equity_symbols(self) -> list[str]:
        """Core equity/HĐTL + active on-demand (deduped)."""
        out: list[str] = []
        seen: set[str] = set()
        for sym in (*self._equity_like_symbols(), *sorted(self._ondemand_active)):
            s = str(sym or "").strip().upper()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    def _build_topics(self) -> list[str]:
        topics = list(self.index_topics)
        for sym in self._all_equity_symbols():
            self._append_quote_topics(topics, sym)
        # de-dupe preserve order
        seen: set[str] = set()
        out: list[str] = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    def _topics_for_channel(self, channel: str, data_topics: list[str]) -> list[str]:
        """Legacy X-Quote / X-Trade channels expect symbol topics, not DATA quote.* patterns."""
        ch = str(channel or "").strip().upper()
        if ch in ("X-QUOTE", "X-TRADE", "MI"):
            return self._all_equity_symbols()
        return data_topics

    def _topics_for_symbols(self, channel: str, symbols: list[str]) -> list[str]:
        ch = str(channel or "").strip().upper()
        if ch in ("X-QUOTE", "X-TRADE", "MI"):
            return list(symbols)
        topics: list[str] = []
        for sym in symbols:
            self._append_quote_topics(topics, sym)
        return topics

    async def _load_ondemand_from_redis(self, redis: aioredis.Redis) -> None:
        raw = await redis.hgetall(ONDEMAND_HASH)
        now = time.time()
        active: set[str] = set()
        for sym, val in (raw or {}).items():
            s = str(sym or "").strip().upper()
            if not s:
                continue
            try:
                last = float(val)
            except (TypeError, ValueError):
                await redis.hdel(ONDEMAND_HASH, sym)
                continue
            if now - last > self._ondemand_idle_sec:
                await redis.hdel(ONDEMAND_HASH, sym)
                continue
            active.add(s)
        self._ondemand_active = active

    async def _reload_core_subscriptions(self, ws: Any, redis: aioredis.Redis) -> None:
        """Rebuild Core YAML from Admin ops + diff SUBSCRIBE/UNSUBSCRIBE (no full restart)."""
        reload_volume_filter()
        self._load_ops_flags()
        if self._maintenance_mode:
            log(COMPONENT, "SSI-OPS-MAINT", "maintenance_mode on — skip core rebuild")
            return
        old_core = set(self._equity_like_symbols())
        try:
            from backend.core_symbols_builder import build_core_symbols
            from backend.market_catalog import clear_catalog_cache

            build_core_symbols()
            clear_catalog_cache()
        except Exception as exc:  # noqa: BLE001
            log(
                COMPONENT,
                "SSI-CORE-REBUILD",
                "core rebuild failed — keep previous symbols",
                logging.WARNING,
                error_code=ERR_PB_SSI_SESSION,
                exc=exc,
            )
            return
        new_list = _default_core_symbols()
        if not new_list:
            log(COMPONENT, "SSI-CORE-REBUILD", "empty core after rebuild — abort")
            return
        self.symbols = list(new_list)
        new_core = set(self._equity_like_symbols())
        added = sorted(new_core - old_core)
        removed = sorted(old_core - new_core)
        # Giữ subscribe nếu mã vẫn on-demand (watchlist/search).
        drop_board = [s for s in removed if s not in self._ondemand_active]
        for ch in self.channels:
            if added:
                topics = self._topics_for_symbols(ch, added)
                if topics:
                    await ws.send(
                        json.dumps({"method": "SUBSCRIBE", "channel": ch, "topics": topics})
                    )
            if drop_board:
                topics = self._topics_for_symbols(ch, drop_board)
                if topics:
                    await ws.send(
                        json.dumps({"method": "UNSUBSCRIBE", "channel": ch, "topics": topics})
                    )
        purged = await self._purge_removed_core_from_board(redis, drop_board)
        log(
            COMPONENT,
            "SSI-CORE-RELOAD",
            "core symbols hot-reloaded",
            added=len(added),
            removed=len(removed),
            purged=purged,
            core=len(new_core),
            sample_added=added[:12],
            sample_removed=removed[:12],
        )
        # Cold-start: seed OHLCV (then optional REST) so Admin-added HNX/UPCOM
        # không hiện stub trống trên iBoard trước khi có tick.
        try:
            await self._seed_missing_core_ohlcv(redis, symbols=added or sorted(new_core))
        except Exception as exc:  # noqa: BLE001
            log(
                COMPONENT,
                "SSI-CORE-SEED",
                "ohlcv cold-start seed failed",
                logging.WARNING,
                error_code=ERR_PB_SSI_SESSION,
                exc=exc,
            )

    async def _purge_removed_core_from_board(
        self,
        redis: aioredis.Redis,
        symbols: list[str],
    ) -> int:
        """HDEL + WS remove cho mã rời Core — FE/iBoard bỏ hàng thừa ngay."""
        purged = 0
        for sym in symbols:
            s = str(sym or "").strip().upper()
            if not s:
                continue
            self._board.pop(s, None)
            try:
                await redis.hdel(HASH_KEY, s)
                remove = json.dumps(
                    {"type": "remove", "symbol": s},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                await redis.publish(CHANNEL, remove)
                purged += 1
            except Exception as exc:  # noqa: BLE001
                log(
                    COMPONENT,
                    "SSI-CORE-PURGE",
                    "failed to purge removed core symbol",
                    logging.WARNING,
                    error_code=ERR_PB_SSI_SESSION,
                    exc=exc,
                    symbol=s,
                )
        return purged

    async def _seed_missing_core_ohlcv(
        self,
        redis: aioredis.Redis,
        *,
        symbols: list[str] | None = None,
    ) -> None:
        """Publish OHLCV last-close for Core symbols missing displayable last/ref."""
        from backend.market_catalog import resolve_listed_exchange
        from backend.portfolio_quotes import DEFAULT_BARS_DIR, ohlcv_last_close_vnd
        from backend.ssi_rest_bootstrap import needs_rest_bootstrap
        from backend.tick_contract import build_tick, tick_kind_for_symbol

        bars = Path(os.getenv("OHLCV_BARS_DIR") or str(DEFAULT_BARS_DIR))
        targets = [
            str(s).strip().upper()
            for s in (symbols or self.symbols or [])
            if str(s).strip() and str(s).strip().upper() not in INDEX_BOARD_SYMBOLS
        ]
        need = [s for s in targets if needs_rest_bootstrap(self._board.get(s))]
        if not need:
            return
        seeded = 0
        for sym in need:
            try:
                px = ohlcv_last_close_vnd(bars, sym)
            except Exception:
                px = None
            if px is None or px <= 0:
                continue
            tick = build_tick(
                symbol=sym,
                last=px,
                ref=px,
                kind=tick_kind_for_symbol(sym),
                exchange=resolve_listed_exchange(sym),
                volume=0,
                change=0,
                change_pct=0.0,
                source="OHLCV_SNAP",
                extra={"bootstrap": "core_cold_start"},
            )
            await self._publish(redis, tick, merged=False)
            seeded += 1
        log(
            COMPONENT,
            "SSI-CORE-SEED",
            "ohlcv cold-start seeded",
            need=len(need),
            seeded=seeded,
            bars_dir=str(bars),
        )

    async def _listen_admin_config_reload(self) -> None:
        """Pub/Sub ``admin:config-reload`` → flag pending core/volume reload."""
        from backend.admin_config_bus import config_reload_channel

        channel = config_reload_channel()
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(channel)
            log(COMPONENT, "SSI-CFG-SUB", "listening admin config reload", channel=channel)
            while not self._stop.is_set():
                try:
                    msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=2.0)
                except asyncio.TimeoutError:
                    continue
                if not msg or msg.get("type") != "message":
                    continue
                raw = msg.get("data")
                reload_core = True
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else {}
                    if isinstance(payload, dict) and "reload_core" in payload:
                        reload_core = bool(payload.get("reload_core"))
                    if isinstance(payload, dict) and isinstance(payload.get("priceboard"), dict):
                        pb = payload["priceboard"]
                        if "ondemand_sync_enabled" in pb:
                            self._ondemand_sync_enabled = bool(pb.get("ondemand_sync_enabled"))
                        if "maintenance_mode" in pb:
                            self._maintenance_mode = bool(pb.get("maintenance_mode"))
                        reload_core = bool(pb.get("reload_core_on_save", reload_core))
                except Exception:
                    pass
                reload_volume_filter()
                if reload_core:
                    self._pending_ops_reload = True
                log(
                    COMPONENT,
                    "SSI-CFG-EVENT",
                    "admin config reload received",
                    reload_core=reload_core,
                )
        except Exception as exc:  # noqa: BLE001
            log(
                COMPONENT,
                "SSI-CFG-SUB",
                "admin config listener stopped",
                logging.WARNING,
                error_code=ERR_PB_SSI_SESSION,
                exc=exc,
            )
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass
            try:
                await redis.aclose()
            except Exception:
                pass

    async def _sync_ondemand_subscriptions(self, ws: Any, redis: aioredis.Redis) -> None:
        """SUBSCRIBE new / UNSUBSCRIBE idle on-demand symbols (poll Redis hash)."""
        if not self._ondemand_sync_enabled:
            return
        raw = await redis.hgetall(ONDEMAND_HASH)
        now = time.time()
        wanted: set[str] = set()
        for sym, val in (raw or {}).items():
            s = str(sym or "").strip().upper()
            if not s:
                continue
            try:
                last = float(val)
            except (TypeError, ValueError):
                await redis.hdel(ONDEMAND_HASH, sym)
                continue
            if now - last > self._ondemand_idle_sec:
                await redis.hdel(ONDEMAND_HASH, sym)
                continue
            wanted.add(s)

        core_like = set(self._equity_like_symbols())
        wanted -= core_like  # core already subscribed at session start
        new = sorted(wanted - self._ondemand_active)
        gone = sorted(self._ondemand_active - wanted)
        if not new and not gone:
            return

        for ch in self.channels:
            if new:
                topics = self._topics_for_symbols(ch, new)
                if topics:
                    await ws.send(
                        json.dumps({"method": "SUBSCRIBE", "channel": ch, "topics": topics})
                    )
            if gone:
                topics = self._topics_for_symbols(ch, gone)
                if topics:
                    await ws.send(
                        json.dumps({"method": "UNSUBSCRIBE", "channel": ch, "topics": topics})
                    )

        self._ondemand_active = wanted
        log(
            COMPONENT,
            "SSI-ONDEMAND-SYNC",
            "ondemand subscribe sync",
            added=new[:20],
            removed=gone[:20],
            active=len(wanted),
        )

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
        # Fill gaps REST missed (thin HNX/UPCOM / off-hours) from local OHLCV.
        try:
            await self._seed_missing_core_ohlcv(redis)
        except Exception as exc:  # noqa: BLE001
            log(
                COMPONENT,
                "SSI-CORE-SEED",
                "post-rest ohlcv seed failed",
                logging.WARNING,
                error_code=ERR_PB_SSI_SESSION,
                exc=exc,
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
        # Keep board tabs accurate for Admin Core (listing > SSI default HOSE).
        if str(tick.get("kind") or "").lower() != "index":
            try:
                from backend.market_catalog import resolve_listed_exchange

                tick["exchange"] = resolve_listed_exchange(sym)
            except Exception:
                pass
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
            full_body = json.dumps(tick, ensure_ascii=False, separators=(",", ":"))
            ws_body = json.dumps(slim_ws_tick(tick), ensure_ascii=False, separators=(",", ":"))
            await redis.hset(HASH_KEY, sym, full_body)
            await redis.publish(CHANNEL, ws_body)
            await record_index_spark(redis, tick)
            await record_equity_spark(redis, tick)
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
        cfg_task = asyncio.create_task(self._listen_admin_config_reload(), name="ssi-admin-cfg")
        try:
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
        finally:
            cfg_task.cancel()
            try:
                await cfg_task
            except (asyncio.CancelledError, Exception):
                pass

    async def _session(self) -> None:
        api_key, api_secret = _ssi_credentials()
        if not api_key or not api_secret:
            raise RuntimeError("missing SSI_CONSUMER_ID / SSI_CONSUMER_SECRET")

        token = await asyncio.to_thread(fetch_access_token, self.auth_url, api_key, api_secret)
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            # Apply Admin-First allocation before subscribe (overlay → rebuild YAML)
            try:
                from backend.core_symbols_builder import build_core_symbols
                from backend.market_catalog import clear_catalog_cache

                build_core_symbols()
                clear_catalog_cache()
                rebuilt = _default_core_symbols()
                if rebuilt:
                    self.symbols = list(rebuilt)
                reload_volume_filter()
                self._load_ops_flags()
            except Exception as exc:  # noqa: BLE001
                log(
                    COMPONENT,
                    "SSI-CORE-BOOT",
                    "core rebuild at boot skipped",
                    logging.WARNING,
                    error_code=ERR_PB_SSI_SESSION,
                    exc=exc,
                )
            await self._load_board_from_redis(redis)
            await self._load_ondemand_from_redis(redis)
            topics = self._build_topics()
            await self._bootstrap_rest(redis, token)
            headers = {"Authorization": f"Bearer {token}"}
            log(
                COMPONENT,
                "SSI-LIVE-CONNECT",
                "connecting ssi websocket",
                ws_url=self.ws_url,
                channels=self.channels,
                topics=len(topics),
                ondemand=len(self._ondemand_active),
            )
            async with websockets.connect(
                self.ws_url,
                additional_headers=headers,
                ping_interval=None,
                max_size=8 * 1024 * 1024,
            ) as ws:
                for ch in self.channels:
                    ch_topics = self._topics_for_channel(ch, topics)
                    sub = {"method": "SUBSCRIBE", "channel": ch, "topics": ch_topics}
                    await ws.send(json.dumps(sub))
                    if str(ch).upper() in ("X-QUOTE", "X-TRADE", "DATA"):
                        fut_topics = [
                            t
                            for t in ch_topics
                            if any(c in str(t) for c in self._contract_to_board)
                        ]
                        log(
                            COMPONENT,
                            "SSI-LIVE-SUBSCRIBED",
                            "ssi channel subscribed",
                            channel=ch,
                            topics=len(ch_topics),
                            futures_topics=fut_topics[:12],
                        )
                log(COMPONENT, "SSI-LIVE-SUBSCRIBED", "ssi channels subscribed", channels=self.channels)

                ondemand_every = 5.0
                last_ondemand_sync = 0.0
                while not self._stop.is_set():
                    now = time.time()
                    if self._pending_ops_reload:
                        self._pending_ops_reload = False
                        try:
                            await self._reload_core_subscriptions(ws, redis)
                        except Exception as exc:  # noqa: BLE001
                            log(
                                COMPONENT,
                                "SSI-CORE-RELOAD-ERR",
                                "core hot-reload failed",
                                logging.WARNING,
                                error_code=ERR_PB_SSI_SESSION,
                                exc=exc,
                            )
                    if now - last_ondemand_sync >= ondemand_every:
                        last_ondemand_sync = now
                        try:
                            await self._sync_ondemand_subscriptions(ws, redis)
                        except Exception as exc:  # noqa: BLE001
                            log(
                                COMPONENT,
                                "SSI-ONDEMAND-ERR",
                                "ondemand sync failed",
                                logging.WARNING,
                                error_code=ERR_PB_SSI_SESSION,
                                exc=exc,
                            )
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
                    parsed = self._remap_futures_symbol(parsed)
                    if parsed.get("contract") or parsed.get("symbol") in FUTURES_BOARD_SYMBOLS:
                        now = time.time()
                        if now - self._futures_sample_at >= 20.0:
                            self._futures_sample_at = now
                            log(
                                COMPONENT,
                                "DBG-20261026-HDT-SSI-SAMPLE",
                                "futures envelope sample",
                                channel=channel,
                                symbol=parsed.get("symbol"),
                                contract=parsed.get("contract"),
                                last=parsed.get("last"),
                                bid1=parsed.get("bid1"),
                                ask1=parsed.get("ask1"),
                                bidVol1=parsed.get("bidVol1"),
                                askVol1=parsed.get("askVol1"),
                                body_keys=sorted(
                                    (msg.get("data") or {}).keys()
                                    if isinstance(msg.get("data"), dict)
                                    else []
                                )[:40],
                            )
                    tick = self._merge_tick(parsed)
                    if parsed.get("contract"):
                        extra = dict(tick.get("extra") or {})
                        extra["contract"] = parsed["contract"]
                        tick["extra"] = extra
                    if not tick_has_payload(tick):
                        continue
                    await self._publish(redis, tick, merged=True)
        finally:
            await redis.aclose()
            log(COMPONENT, "SSI-LIVE-SESSION-END", "ssi live session ended", t=int(time.time()))
