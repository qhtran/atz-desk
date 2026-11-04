"""Async Telegram Bot API client for Desk price alerts (httpx)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from backend.observability import ERR_PB_ALERT_TG, log, setup

setup("desk_alerts")
COMPONENT = "desk_alerts"

DEFAULT_API_BASE = "https://api.telegram.org"


def telegram_bot_token() -> str:
    return (
        os.getenv("DESK_ALERTS_TELEGRAM_BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()


def telegram_api_base() -> str:
    return (os.getenv("DESK_ALERTS_TELEGRAM_API_BASE") or DEFAULT_API_BASE).rstrip("/")


def telegram_enabled() -> bool:
    flag = (os.getenv("DESK_ALERTS_TELEGRAM") or "1").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    return bool(telegram_bot_token())


def resolve_chat_id(user_id: str) -> str | None:
    """Map ``user_id`` → chat_id từ env JSON hoặc fallback chat mặc định."""
    user = str(user_id or "").strip()
    raw_map = (os.getenv("DESK_ALERTS_TELEGRAM_CHAT_IDS") or "").strip()
    if raw_map:
        try:
            data = json.loads(raw_map)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and user:
            val = data.get(user) or data.get(user.lower())
            if val is not None and str(val).strip():
                return str(val).strip()
    fallback = (
        os.getenv("DESK_ALERTS_TELEGRAM_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    return fallback or None


def format_alert_message(cfg: dict[str, Any], last_price: float) -> str:
    sym = str(cfg.get("symbol") or "").upper()
    cond = str(cfg.get("condition") or "").upper()
    target = cfg.get("target_value")
    op = ">" if cond == "GT" else "<" if cond == "LT" else cond
    return (
        f"ATZ Desk alert · {sym}\n"
        f"Điều kiện: giá {op} {target}\n"
        f"Giá hiện tại: {last_price}"
    )


async def send_telegram_message(
    chat_id: str,
    text: str,
    *,
    timeout_sec: float = 10.0,
    client: Any | None = None,
) -> dict[str, Any]:
    """Gọi ``sendMessage``. Raise ``RuntimeError`` khi HTTP/API lỗi (worker bắt)."""
    import httpx

    token = telegram_bot_token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    cid = str(chat_id or "").strip()
    if not cid:
        raise RuntimeError("telegram chat_id missing")
    url = f"{telegram_api_base()}/bot{token}/sendMessage"
    payload = {"chat_id": cid, "text": text, "disable_web_page_preview": True}
    owns = client is None
    http = client or httpx.AsyncClient(timeout=timeout_sec)
    try:
        resp = await http.post(url, json=payload)
    except httpx.TimeoutException as exc:
        log(
            COMPONENT,
            "TG-TIMEOUT",
            "telegram sendMessage timeout",
            logging.WARNING,
            error_code=ERR_PB_ALERT_TG,
            exc=exc,
            chat_id=cid,
        )
        raise RuntimeError("telegram timeout") from exc
    except httpx.HTTPError as exc:
        log(
            COMPONENT,
            "TG-HTTP",
            "telegram sendMessage http error",
            logging.WARNING,
            error_code=ERR_PB_ALERT_TG,
            exc=exc,
            chat_id=cid,
        )
        raise RuntimeError("telegram http error") from exc
    finally:
        if owns:
            await http.aclose()

    if resp.status_code == 429:
        log(
            COMPONENT,
            "TG-RATE",
            "telegram rate limited",
            logging.WARNING,
            error_code=ERR_PB_ALERT_TG,
            chat_id=cid,
            status=resp.status_code,
        )
        raise RuntimeError("telegram rate limited")
    if resp.status_code >= 400:
        log(
            COMPONENT,
            "TG-FAIL",
            "telegram sendMessage rejected",
            logging.WARNING,
            error_code=ERR_PB_ALERT_TG,
            chat_id=cid,
            status=resp.status_code,
            body=(resp.text or "")[:200],
        )
        raise RuntimeError(f"telegram HTTP {resp.status_code}")
    try:
        data = resp.json()
    except Exception:
        data = {}
    if isinstance(data, dict) and data.get("ok") is False:
        raise RuntimeError(str(data.get("description") or "telegram api ok=false"))
    return data if isinstance(data, dict) else {"ok": True}
