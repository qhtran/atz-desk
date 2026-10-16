"""Adapters: Telegram (primary), Email Brevo, In-app. Không bao giờ log token/key."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


class ChannelError(Exception):
    pass


def format_text(sig: dict) -> str:
    arrow = "🟢 MUA" if sig["direction"] == "BUY" else "🔴 BÁN"
    return (f"{arrow} {sig['symbol']} @ {sig['price']:,.0f}\n"
            f"Bộ lọc: {sig['filter_name']} | tin cậy {float(sig['confidence']):.0%}\n"
            f"{sig['reason']}\n{sig['timestamp']} | {sig['signal_id']}")


def _retry(fn, retries: int):
    last = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries:
                time.sleep(min(2 ** attempt, 4))
    raise ChannelError(_safe(last))


def _safe(e) -> str:
    """Thông điệp lỗi đã xoá token."""
    msg = f"{type(e).__name__}: {e}"
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    for s in filter(None, [tok, os.environ.get("BREVO_SMTP_KEY")]):
        msg = msg.replace(s, "***")
    return msg[:300]


class TelegramAdapter:
    name = "telegram"

    def __init__(self, timeout: float, retries: int, token: str | None = None):
        self.timeout, self.retries = timeout, retries
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")

    def send(self, chat_id, text: str) -> str:
        if not self.token:
            raise ChannelError("thiếu TELEGRAM_BOT_TOKEN")

        def once():
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data=json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode(),
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.load(resp)
            except urllib.error.HTTPError as e:
                raise ChannelError(f"HTTP {e.code}") from None
            if not body.get("ok"):
                raise ChannelError(f"telegram ok=false {body.get('description', '')[:100]}")
            return str(body["result"]["message_id"])
        return _retry(once, self.retries)


class EmailAdapter:
    name = "email"

    def __init__(self, retries: int, sender=None):
        from engine.notify import BrevoSender
        self.retries, self.sender = retries, sender or BrevoSender()

    def send(self, to: str, subject: str, text: str) -> str:
        _retry(lambda: self.sender.send_email(to, subject, text), self.retries)
        return "smtp"


class InAppAdapter:
    name = "inapp"

    def __init__(self, r, max_per_user: int):
        self.r, self.max = r, max_per_user

    def send(self, user_id: str, sig: dict) -> str:
        key = f"inapp:{user_id}"
        self.r.lpush(key, json.dumps(sig, ensure_ascii=False))
        self.r.ltrim(key, 0, self.max - 1)
        return key
