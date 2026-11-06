"""Redis Pub/Sub bus for Admin control-plane hot-reload (dev.atz.vn)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import redis.asyncio as aioredis

from backend.observability import ERR_PB_REDIS, log, setup
from backend.redis_listener import REDIS_URL

setup("admin")
COMPONENT = "admin"

DEFAULT_CHANNEL = "admin:config-reload"


def config_reload_channel() -> str:
    return (os.getenv("ADMIN_CONFIG_RELOAD_CHANNEL") or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL


def build_reload_message(
    stream_alerts: dict[str, Any] | None = None,
    *,
    min_traded_value: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "type": "config_reload",
        "source": "admin_control_plane",
        "ts": int(time.time()),
        "channel": config_reload_channel(),
    }
    if isinstance(stream_alerts, dict) and stream_alerts:
        payload["stream_alerts"] = stream_alerts
    if isinstance(min_traded_value, dict) and min_traded_value:
        payload["min_traded_value"] = min_traded_value
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


async def publish_config_reload(
    stream_alerts: dict[str, Any] | None = None,
    *,
    min_traded_value: dict[str, Any] | None = None,
    redis_url: str | None = None,
) -> bool:
    """Publish reload event so other workers apply screening thresholds."""
    from backend.core_selector import MIN_TRADED_VALUE_KEY

    channel = config_reload_channel()
    body = build_reload_message(stream_alerts, min_traded_value=min_traded_value)
    redis = aioredis.from_url(redis_url or REDIS_URL, decode_responses=True)
    try:
        receivers = await redis.publish(channel, body)
        if isinstance(min_traded_value, dict) and min_traded_value:
            await redis.set(
                MIN_TRADED_VALUE_KEY,
                json.dumps(min_traded_value, ensure_ascii=False, separators=(",", ":")),
            )
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
