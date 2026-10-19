"""`python -m ingestion.ssi_stream` — container atz-ssi-stream (ADR 0008 Phase 1)."""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import redis

from ingestion.index.series import in_session
from ingestion.log import ERR_SYS_CONFIG, setup
from ingestion.ssi_stream.auth import fetch_token
from ingestion.ssi_stream.client import SsiStreamClient, log
from ingestion.ssi_stream.config import load
from ingestion.ssi_stream.parse import parse_market_message
from ingestion.ssi_stream.writer import RedisWriter

RUNNING = True


def _stop(*_):
    global RUNNING
    RUNNING = False


def main() -> None:
    setup(os.environ.get("SSI_STREAM_LOG_LEVEL", "INFO"))
    try:
        s = load()
    except Exception as err:  # noqa: BLE001
        log("HEALTH", f"config load failed: {err}", logging.ERROR, error_code=ERR_SYS_CONFIG)
        sys.exit(1)

    if not s.enabled or s.mode == "rest_only":
        log("HEALTH", "ssi_stream disabled (enabled=false or mode=rest_only); exit 0")
        return
    if not (s.consumer_id and s.consumer_secret):
        log("HEALTH", "missing SSI_CONSUMER_ID/SECRET; exit 0 (index REST backup vẫn chạy)", logging.WARNING)
        return

    r = redis.Redis.from_url(s.redis_url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3)
    writer = RedisWriter(s, r)
    token_box: dict = {"tok": None, "exp": 0.0}
    state: dict = {"phase": "init", "detail": {}}

    def token_provider() -> str:
        now = time.time()
        if token_box["tok"] and now < token_box["exp"]:
            return token_box["tok"]
        tok, exp = fetch_token(s.auth_url, s.consumer_id, s.consumer_secret)
        token_box["tok"], token_box["exp"] = tok, exp
        return tok

    def on_message(msg: dict) -> None:
        parsed = parse_market_message(msg, s.aliases)
        if not parsed:
            return
        writer.upsert_quote(parsed)

    def on_state(phase: str, detail: dict) -> None:
        state["phase"] = phase
        state["detail"] = detail

    backoff = s.reconnect_initial
    client = None
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log("HEALTH", f"start url={s.url} topics={len(s.topics)} mode={s.mode}")

    while RUNNING:
        if client is None:
            client = SsiStreamClient(
                url=s.url,
                topics=s.topics,
                token_provider=token_provider,
                on_message=on_message,
                on_state=on_state,
                auth_payload={
                    "api_key": s.consumer_id,
                    "api_secret": s.consumer_secret,
                },
            )
            client.start()
            backoff = s.reconnect_initial

        now = time.time()
        trading = in_session(now, s.timezone, s.sessions)
        silence = s.silence_trading if trading else s.silence_off
        last = client.last_msg_at or 0.0
        age = (now - last) if last else 1e9
        healthy = bool(client.connected and age <= silence)
        try:
            r.set(
                s.health_key,
                json.dumps({
                    "epoch": now,
                    "ts": datetime.fromtimestamp(now, ZoneInfo(s.timezone)).isoformat(timespec="seconds"),
                    "healthy": healthy,
                    "connected": client.connected,
                    "phase": state.get("phase"),
                    "msg_count": client.msg_count,
                    "err_count": client.err_count,
                    "last_msg_age_sec": None if not last else round(age, 1),
                    "quotes": {k: v.value for k, v in writer.last.items()},
                    "source": "SSI_WS",
                }),
                ex=3600,
            )
        except Exception as err:  # noqa: BLE001
            log("REDIS", f"health write failed: {err}", logging.ERROR)

        if not client.connected and not RUNNING:
            break
        # Reconnect nếu thread chết
        if client._thread and not client._thread.is_alive() and RUNNING:
            log("WS", f"thread dead; restart backoff={backoff:.0f}s", logging.WARNING)
            try:
                client.stop()
            except Exception:  # noqa: BLE001
                pass
            client = None
            time.sleep(backoff)
            backoff = min(s.reconnect_max, backoff * 2)
            continue

        time.sleep(1)

    if client:
        client.stop()
    log("HEALTH", "stopped")


if __name__ == "__main__":
    main()
