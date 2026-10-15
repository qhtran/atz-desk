"""Cooldown theo user, mã, filter và ngày nến. Mail tắt hoặc lỗi sender không vỡ luồng."""

from __future__ import annotations

import sqlite3

from engine.notify import MockSender, maybe_notify
from storage.repository import ensure_user, notification_sent, record_signal, set_user_settings


class _Boom:
    def send_email(self, to: str, subject: str, body: str) -> None:
        raise RuntimeError("smtp")


def _signal(db: sqlite3.Connection, user_id: int, day: str = "2026-10-15") -> int:
    signal_id, _created = record_signal(db, user_id, "FPT", "rsi", "mua", day)
    return signal_id


def test_sends_once_for_the_same_bar(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local", "a@example.com")
    set_user_settings(db, user_id, {"email_bat": True, "loai_nhan": ["mua"]}, "a@example.com")
    signal_id = _signal(db, user_id)
    sender = MockSender()
    assert maybe_notify(db, user_id, signal_id, "FPT", "rsi", "2026-10-15", "mua", "dưới 30", 90, sender) == "gửi"
    assert maybe_notify(db, user_id, signal_id, "FPT", "rsi", "2026-10-15", "mua", "dưới 30", 90, sender) == "cooldown"
    assert len(sender.sent) == 1
    assert notification_sent(db, user_id, "FPT", "rsi", "2026-10-15") is True


def test_a_new_bar_date_sends_again(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local", "a@example.com")
    set_user_settings(db, user_id, {"email_bat": True}, "a@example.com")
    sender = MockSender()
    first = _signal(db, user_id, "2026-10-15")
    second = _signal(db, user_id, "2026-10-16")
    assert maybe_notify(db, user_id, first, "FPT", "rsi", "2026-10-15", "mua", "a", 90, sender) == "gửi"
    assert maybe_notify(db, user_id, second, "FPT", "rsi", "2026-10-16", "mua", "b", 91, sender) == "gửi"
    assert len(sender.sent) == 2


def test_disabled_mail_does_not_send(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local", "a@example.com")
    set_user_settings(db, user_id, {"email_bat": False}, "a@example.com")
    sender = MockSender()
    signal_id = _signal(db, user_id)
    assert maybe_notify(db, user_id, signal_id, "FPT", "rsi", "2026-10-15", "mua", "a", 90, sender) == "tắt"
    assert sender.sent == []


def test_sender_error_is_logged_and_swallowed(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local", "a@example.com")
    set_user_settings(db, user_id, {"email_bat": True}, "a@example.com")
    signal_id = _signal(db, user_id)
    assert maybe_notify(db, user_id, signal_id, "FPT", "rsi", "2026-10-15", "mua", "a", 90, _Boom()) == "lỗi"
    assert notification_sent(db, user_id, "FPT", "rsi", "2026-10-15") is False
