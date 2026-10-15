"""Brevo SMTP đọc biến môi trường. Test không mở kết nối thật."""

from __future__ import annotations

import sqlite3

import pytest

from engine.notify import BrevoSender, maybe_notify
from storage.repository import ensure_user, notification_sent, record_signal, set_user_settings


class _FakeSMTP:
    def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started = False
        self.login_args: tuple[str, str] | None = None
        self.message = None

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *args: object) -> bool:
        return False

    def ehlo(self) -> None:
        return None

    def starttls(self) -> None:
        self.started = True

    def login(self, login: str, key: str) -> None:
        self.login_args = (login, key)

    def send_message(self, message: object) -> None:
        self.message = message


def test_brevo_uses_starttls_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[_FakeSMTP] = []

    def _open(host: str, port: int, timeout: int | None = None) -> _FakeSMTP:
        client = _FakeSMTP(host, port, timeout)
        opened.append(client)
        return client

    monkeypatch.setenv("BREVO_SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("BREVO_SMTP_PORT", "587")
    monkeypatch.setenv("BREVO_SMTP_LOGIN", "login-from-env")
    monkeypatch.setenv("BREVO_SMTP_KEY", "key-from-env")
    monkeypatch.setenv("BREVO_SENDER_EMAIL", "mail@atz.vn")
    monkeypatch.setenv("BREVO_SENDER_NAME", "ATZ")
    monkeypatch.setattr("engine.notify.smtplib.SMTP", _open)
    BrevoSender().send_email("reader@example.com", "FPT mua", "nội dung")
    client = opened[0]
    assert client.host == "smtp-relay.brevo.com"
    assert client.port == 587
    assert client.started is True
    assert client.login_args == ("login-from-env", "key-from-env")
    assert client.message is not None
    assert client.message["From"] == "ATZ <mail@atz.vn>"
    assert client.message["To"] == "reader@example.com"


def test_missing_key_does_not_open_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BREVO_SMTP_LOGIN", raising=False)
    monkeypatch.delenv("BREVO_SMTP_KEY", raising=False)
    called = False

    def _open(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("không được mở SMTP")

    monkeypatch.setattr("engine.notify.smtplib.SMTP", _open)
    with pytest.raises(RuntimeError, match="BREVO_SMTP_KEY"):
        BrevoSender().send_email("reader@example.com", "FPT", "nội dung")
    assert called is False


def test_brevo_failure_is_logged_and_engine_continues(db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BREVO_SMTP_LOGIN", raising=False)
    monkeypatch.delenv("BREVO_SMTP_KEY", raising=False)
    user_id = ensure_user(db, "local", "a@example.com")
    set_user_settings(db, user_id, {"email_bat": True}, "a@example.com")
    signal_id, _created = record_signal(db, user_id, "FPT", "rsi", "mua", "2026-10-15")
    assert maybe_notify(db, user_id, signal_id, "FPT", "rsi", "2026-10-15", "mua", "a", 90, BrevoSender()) == "lỗi"
    assert notification_sent(db, user_id, "FPT", "rsi", "2026-10-15") is False
