"""Redis Pub/Sub bus for Admin control-plane hot-reload (dev.atz.vn)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from backend.observability import ERR_PB_REDIS, log, setup

setup("admin")
COMPONENT = "admin"

DEFAULT_CHANNEL = "admin:config-reload"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def config_reload_channel() -> str:
    return (os.getenv("ADMIN_CONFIG_RELOAD_CHANNEL") or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL


def build_reload_message(
    stream_alerts: dict[str, Any] | None = None,
    priceboard: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "config_reload",
        "source": "admin_control_plane",
        "ts": int(time.time()),
        "channel": config_reload_channel(),
    }
    if isinstance(stream_alerts, dict) and stream_alerts:
        payload["stream_alerts"] = stream_alerts
    if isinstance(priceboard, dict) and priceboard:
        payload["priceboard"] = priceboard
        payload["reload_core"] = bool(priceboard.get("reload_core_on_save", True))
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


async def publish_config_reload(
    stream_alerts: dict[str, Any] | None = None,
    *,
    priceboard: dict[str, Any] | None = None,
    redis_url: str | None = None,
) -> bool:
    """Publish reload event so workers apply screening / Core / volume settings."""
    import redis.asyncio as aioredis

    channel = config_reload_channel()
    body = build_reload_message(stream_alerts, priceboard=priceboard)
    redis = aioredis.from_url(redis_url or REDIS_URL, decode_responses=True)
    try:
        receivers = await redis.publish(channel, body)
        log(
            COMPONENT,
            "CFG-PUB",
            "admin config reload published",
            channel=channel,
            receivers=receivers,
        )
        return True
    except Exception as exc:
        log(
            COMPONENT,
            "CFG-PUB",
            "admin config reload publish failed",
            logging.WARNING,
            error_code=ERR_PB_REDIS,
            exc=exc,
            channel=channel,
        )
        return False
    finally:
        await redis.aclose()
