"""Gửi email qua một sender. Cooldown là khóa user + mã + filter + ngày nến."""

from __future__ import annotations

import os
import smtplib
import sqlite3
from email.message import EmailMessage
from typing import Protocol

from storage.repository import (
    DuplicateNotification,
    get_user,
    log_notification,
    mark_signal_notified,
    notification_sent,
)

_DEFAULT_HOST = "smtp-relay.brevo.com"
_DEFAULT_PORT = 587
_DEFAULT_SENDER = "mail@atz.vn"


class MailSender(Protocol):
    def send_email(self, to: str, subject: str, body: str) -> None:
        """Gửi một thư. Lỗi gửi thì ném exception."""


class MockSender:
    """Ghi lại thư thay vì gửi SMTP. Dùng trong pytest."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send_email(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


class BrevoSender:
    """SMTP Brevo qua STARTTLS. Login và key chỉ lấy từ biến môi trường."""

    def send_email(self, to: str, subject: str, body: str) -> None:
        host = os.environ.get("BREVO_SMTP_HOST", _DEFAULT_HOST).strip() or _DEFAULT_HOST
        port = int(os.environ.get("BREVO_SMTP_PORT", str(_DEFAULT_PORT)))
        login = os.environ.get("BREVO_SMTP_LOGIN", "").strip()
        key = os.environ.get("BREVO_SMTP_KEY", "").strip()
        sender_email = os.environ.get("BREVO_SENDER_EMAIL", _DEFAULT_SENDER).strip() or _DEFAULT_SENDER
        sender_name = os.environ.get("BREVO_SENDER_NAME", "").strip()
        if not login or not key:
            raise RuntimeError("thiếu BREVO_SMTP_LOGIN hoặc BREVO_SMTP_KEY")
        message = EmailMessage()
        message["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(login, key)
            smtp.send_message(message)


def maybe_notify(
    conn: sqlite3.Connection,
    user_id: int,
    signal_id: int,
    symbol: str,
    filter_name: str,
    bar_date: str,
    signal_type: str,
    reason: str,
    price: float,
    sender: MailSender,
) -> str:
    """Trả 'gửi', 'tắt', 'cooldown' hoặc 'lỗi'. Sender lỗi thì ghi log và không ném ra ngoài."""
    user = get_user(conn, user_id)
    if user is None:
        return "tắt"
    settings = user["cai_dat_chung"] or {}
    if not settings.get("email_bat"):
        return "tắt"
    allowed = settings.get("loai_nhan")
    if allowed is not None and signal_type not in allowed:
        return "tắt"
    email = user["email_nhan_thong_bao"]
    if not email:
        return "tắt"
    if notification_sent(conn, user_id, symbol, filter_name, bar_date):
        return "cooldown"
    subject = f"{symbol} {signal_type}"
    body = f"{symbol} {signal_type} ngày {bar_date}. Giá {price}. {reason}"
    try:
        sender.send_email(email, subject, body)
    except Exception as exc:
        log_notification(conn, user_id, signal_id, "lỗi", email, symbol, filter_name, bar_date, str(exc))
        return "lỗi"
    try:
        log_notification(conn, user_id, signal_id, "thành công", email, symbol, filter_name, bar_date)
    except DuplicateNotification:
        return "cooldown"
    mark_signal_notified(conn, signal_id)
    return "gửi"
