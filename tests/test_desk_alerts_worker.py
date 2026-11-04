"""Desk Telegram Alerts Phase 3–4: tick evaluate, cooldown, Telegram mock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.desk_alerts_store import (
    create_alert_config,
    init_desk_alerts_store,
    is_in_cooldown,
    latest_history_for_config,
    list_active_alerts_for_symbol,
    record_alert_history,
)
from backend.desk_alerts_telegram import format_alert_message, resolve_chat_id
from backend.desk_alerts_worker import (
    DeskAlertsWorker,
    parse_tick_price,
    select_firings,
)


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "desk_alerts.db"
    init_desk_alerts_store(path)
    return path


def test_parse_tick_price():
    assert parse_tick_price('{"symbol":"fpt","last":95.5}') == ("FPT", 95.5)
    assert parse_tick_price({"symbol": "VNM", "last": 0}) is None
    assert parse_tick_price("not-json") is None
    assert parse_tick_price({"tick": {"symbol": "HPG", "last": 28}}) == ("HPG", 28.0)


def test_select_firings_and_cooldown(db: Path):
    gt = create_alert_config("hoa", symbol="FPT", condition="GT", target_value=100, db_path=db)
    lt = create_alert_config("hoa", symbol="FPT", condition="LT", target_value=90, db_path=db)
    configs = list_active_alerts_for_symbol("FPT", db_path=db)
    assert {c["id"] for c in configs} == {gt["id"], lt["id"]}

    now = datetime(2026, 11, 4, 1, 0, tzinfo=timezone.utc)
    fire_hi = select_firings(configs, 101.0, cooldown_sec=900, now=now, in_cooldown_fn=lambda *a, **k: False)
    assert [c["id"] for c in fire_hi] == [gt["id"]]

    fire_lo = select_firings(configs, 89.0, cooldown_sec=900, now=now, in_cooldown_fn=lambda *a, **k: False)
    assert [c["id"] for c in fire_lo] == [lt["id"]]

    # equal target = no fire
    assert select_firings(configs, 100.0, cooldown_sec=900, now=now, in_cooldown_fn=lambda *a, **k: False) == []

    record_alert_history(gt["id"], 101.0, triggered_at=now.isoformat(), db_path=db)
    assert is_in_cooldown(gt["id"], 900, now=now + timedelta(minutes=5), db_path=db) is True
    assert is_in_cooldown(gt["id"], 900, now=now + timedelta(minutes=16), db_path=db) is False


@pytest.mark.asyncio
async def test_worker_tick_records_history_and_respects_cooldown(db: Path, monkeypatch):
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM", "0")
    monkeypatch.setenv("DESK_ALERTS_COOLDOWN_SEC", "900")
    cfg = create_alert_config("hoa", symbol="FPT", condition="GT", target_value=50, db_path=db)
    worker = DeskAlertsWorker(db_path=db)

    fired = await worker.handle_tick_payload({"symbol": "FPT", "last": 55})
    assert len(fired) == 1
    assert fired[0]["id"] == cfg["id"]
    hist = latest_history_for_config(cfg["id"], db_path=db)
    assert hist is not None and hist["last_price"] == 55.0

    fired2 = await worker.handle_tick_payload({"symbol": "FPT", "last": 56})
    assert fired2 == []
    assert worker.stats["skipped_cooldown"] >= 1


@pytest.mark.asyncio
async def test_worker_sends_telegram_mocked(db: Path, monkeypatch):
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM_CHAT_ID", "999001")
    monkeypatch.setenv("DESK_ALERTS_COOLDOWN_SEC", "60")
    create_alert_config("hoa", symbol="VNM", condition="LT", target_value=80, db_path=db)

    calls: list[tuple[str, str]] = []

    async def fake_send(chat_id: str, text: str, **kwargs):
        calls.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr("backend.desk_alerts_worker.send_telegram_message", fake_send)
    worker = DeskAlertsWorker(db_path=db)
    fired = await worker.handle_tick_payload('{"symbol":"VNM","last":79.5}')
    assert len(fired) == 1
    assert calls and calls[0][0] == "999001"
    assert "VNM" in calls[0][1]
    assert worker.stats["tg_ok"] == 1


@pytest.mark.asyncio
async def test_worker_telegram_failure_does_not_raise(db: Path, monkeypatch):
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("DESK_ALERTS_COOLDOWN_SEC", "60")
    create_alert_config("hoa", symbol="HPG", condition="GT", target_value=10, db_path=db)

    async def boom(*args, **kwargs):
        raise RuntimeError("telegram rate limited")

    monkeypatch.setattr("backend.desk_alerts_worker.send_telegram_message", boom)
    worker = DeskAlertsWorker(db_path=db)
    fired = await worker.handle_tick_payload({"symbol": "HPG", "last": 11})
    assert len(fired) == 1  # history recorded; worker continues
    assert worker.stats["tg_fail"] == 1
    assert latest_history_for_config(fired[0]["id"], db_path=db) is not None


def test_resolve_chat_id_map(monkeypatch):
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM_CHAT_IDS", '{"hoa":"111","boss":"222"}')
    monkeypatch.delenv("DESK_ALERTS_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert resolve_chat_id("hoa") == "111"
    assert resolve_chat_id("boss") == "222"
    monkeypatch.setenv("DESK_ALERTS_TELEGRAM_CHAT_ID", "fallback")
    assert resolve_chat_id("unknown") == "fallback"


def test_format_alert_message():
    msg = format_alert_message(
        {"symbol": "FPT", "condition": "GT", "target_value": 100},
        101.5,
    )
    assert "FPT" in msg and ">" in msg and "101.5" in msg
