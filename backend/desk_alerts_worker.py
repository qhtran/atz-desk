"""Redis Pub/Sub → evaluate user price alerts → Telegram (Desk Phase 3–4)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import redis.asyncio as aioredis

from backend.desk_alerts_store import (
    condition_met,
    is_in_cooldown,
    list_active_alerts_for_symbol,
    record_alert_history,
)
from backend.desk_alerts_telegram import (
    format_alert_message,
    resolve_chat_id,
    send_telegram_message,
    telegram_enabled,
)
from backend.observability import ERR_PB_ALERT_TG, ERR_PB_REDIS, log, setup

setup("desk_alerts")
COMPONENT = "desk_alerts"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CHANNEL = os.getenv("PRICEBOARD_CHANNEL", "priceboard_ticks")


def worker_enabled() -> bool:
    """Bật khi ``DESK_ALERTS_WORKER=1`` (mặc định on nếu Telegram token có)."""
    flag = (os.getenv("DESK_ALERTS_WORKER") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    return telegram_enabled()


def cooldown_sec() -> float:
    raw = os.getenv("DESK_ALERTS_COOLDOWN_SEC", "900")
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 900.0


def parse_tick_price(payload: str | bytes | dict[str, Any]) -> tuple[str, float] | None:
    """Trích ``(symbol, last)`` từ tick JSON pub/sub. None nếu thiếu."""
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
    elif isinstance(payload, dict):
        data = payload
    else:
        return None
    if not isinstance(data, dict):
        return None
    # occasional envelope {type, tick}/{data}
    if "symbol" not in data and isinstance(data.get("tick"), dict):
        data = data["tick"]
    elif "symbol" not in data and isinstance(data.get("data"), dict):
        data = data["data"]
    sym = str(data.get("symbol") or "").strip().upper()
    if not sym:
        return None
    try:
        last = float(data.get("last") or 0)
    except (TypeError, ValueError):
        return None
    if last <= 0:
        return None
    return sym, last


def select_firings(
    configs: list[dict[str, Any]],
    last_price: float,
    *,
    cooldown_sec: float,
    now: datetime | None = None,
    in_cooldown_fn: Callable[..., bool] | None = None,
) -> list[dict[str, Any]]:
    """Pure-ish: configs thỏa GT/LT và ngoài cooldown."""
    check = in_cooldown_fn or is_in_cooldown
    current = now or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for cfg in configs:
        if not condition_met(str(cfg.get("condition") or ""), last_price, float(cfg.get("target_value") or 0)):
            continue
        try:
            cooling = bool(
                check(int(cfg["id"]), cooldown_sec, now=current)
            )
        except TypeError:
            cooling = bool(check(int(cfg["id"]), cooldown_sec))
        if cooling:
            continue
        out.append(cfg)
    return out


class DeskAlertsWorker:
    """Long-lived Pub/Sub listener; never crashes the API process on TG/Redis blips."""

    def __init__(
        self,
        *,
        db_path: Path | None = None,
        redis_url: str | None = None,
        channel: str | None = None,
    ) -> None:
        self._db_path = db_path
        self._redis_url = redis_url or REDIS_URL
        self._channel = channel or CHANNEL
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.stats = {"ticks": 0, "fired": 0, "skipped_cooldown": 0, "tg_ok": 0, "tg_fail": 0}

    def start(self) -> None:
        if not worker_enabled():
            log(COMPONENT, "WORKER-OFF", "desk alerts worker disabled")
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="desk-alerts-worker")
        log(
            COMPONENT,
            "WORKER-START",
            "desk alerts worker starting",
            channel=self._channel,
            cooldown_sec=cooldown_sec(),
            telegram=telegram_enabled(),
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log(COMPONENT, "WORKER-STOP", "desk alerts worker stopped")

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
                    "WORKER-LOOP",
                    "desk alerts worker error",
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
        redis = aioredis.from_url(self._redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(self._channel)
            log(COMPONENT, "REDIS-SUB", "subscribed price ticks", channel=self._channel)
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
                await self.handle_tick_payload(data)
        finally:
            try:
                await pubsub.unsubscribe(self._channel)
                await pubsub.aclose()
            except Exception:
                pass
            await redis.aclose()

    async def handle_tick_payload(self, payload: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate one tick; return list of fired configs (for tests)."""
        parsed = parse_tick_price(payload)
        if not parsed:
            return []
        symbol, last_price = parsed
        self.stats["ticks"] += 1
        try:
            configs = list_active_alerts_for_symbol(symbol, db_path=self._db_path)
        except Exception as exc:
            log(
                COMPONENT,
                "DB-LIST",
                "list active alerts failed",
                logging.WARNING,
                error_code=ERR_PB_ALERT_TG,
                exc=exc,
                symbol=symbol,
            )
            return []
        if not configs:
            return []

        cool = cooldown_sec()
        now = datetime.now(timezone.utc)
        firings: list[dict[str, Any]] = []
        for cfg in configs:
            if not condition_met(str(cfg.get("condition") or ""), last_price, float(cfg.get("target_value") or 0)):
                continue
            try:
                if is_in_cooldown(int(cfg["id"]), cool, now=now, db_path=self._db_path):
                    self.stats["skipped_cooldown"] += 1
                    continue
            except Exception as exc:
                log(COMPONENT, "COOLDOWN", "cooldown check failed", logging.WARNING, exc=exc)
                continue
            firings.append(cfg)

        fired: list[dict[str, Any]] = []
        for cfg in firings:
            ok = await self._fire_one(cfg, last_price)
            if ok:
                fired.append(cfg)
                self.stats["fired"] += 1
        return fired

    async def _fire_one(self, cfg: dict[str, Any], last_price: float) -> bool:
        """Record history first (starts cooldown), then Telegram best-effort."""
        try:
            record_alert_history(int(cfg["id"]), last_price, db_path=self._db_path)
        except Exception as exc:
            log(
                COMPONENT,
                "HIST-FAIL",
                "record alert_history failed",
                logging.WARNING,
                error_code=ERR_PB_ALERT_TG,
                exc=exc,
                alert_id=cfg.get("id"),
            )
            return False

        if not telegram_enabled():
            return True

        chat_id = resolve_chat_id(str(cfg.get("user_id") or ""))
        if not chat_id:
            log(
                COMPONENT,
                "TG-NO-CHAT",
                "no telegram chat_id for user",
                logging.WARNING,
                error_code=ERR_PB_ALERT_TG,
                user_id=cfg.get("user_id"),
                alert_id=cfg.get("id"),
            )
            return True

        text = format_alert_message(cfg, last_price)
        try:
            await send_telegram_message(chat_id, text)
            self.stats["tg_ok"] += 1
            log(
                COMPONENT,
                "TG-SENT",
                "telegram alert sent",
                symbol=cfg.get("symbol"),
                alert_id=cfg.get("id"),
                last_price=last_price,
            )
        except Exception as exc:
            self.stats["tg_fail"] += 1
            log(
                COMPONENT,
                "TG-SEND-FAIL",
                "telegram alert send failed (worker continues)",
                logging.WARNING,
                error_code=ERR_PB_ALERT_TG,
                exc=exc,
                alert_id=cfg.get("id"),
            )
        return True
