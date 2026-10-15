"""Schema và repository. Mỗi test dùng DB trong thư mục tạm."""

from __future__ import annotations

import sqlite3

import pytest

from storage.repository import (
    DuplicateNotification,
    add_composite_rule,
    delete_filter_configs,
    ensure_user,
    get_market_bar,
    get_user,
    get_user_by_username,
    list_composite_rules,
    list_filter_configs,
    list_signals,
    log_notification,
    notification_sent,
    record_signal,
    save_filter_config,
    save_market_bar,
    set_user_settings,
)


def test_ensure_user_is_idempotent_and_settings_round_trip(db: sqlite3.Connection) -> None:
    first = ensure_user(db, "local", "a@example.com")
    again = ensure_user(db, " local ")
    assert first == again
    set_user_settings(db, first, {"email_bat": True, "loai_nhan": ["mua"]}, "b@example.com")
    user = get_user(db, first)
    assert user is not None
    assert user["email_nhan_thong_bao"] == "b@example.com"
    assert user["cai_dat_chung"] == {"email_bat": True, "loai_nhan": ["mua"]}
    assert get_user_by_username(db, "local")["id"] == first


def test_filter_configs_stay_inside_one_user(db: sqlite3.Connection) -> None:
    alice = ensure_user(db, "alice")
    bob = ensure_user(db, "bob")
    save_filter_config(db, alice, "rsi", {"length": 14}, enabled=True, thu_tu=1)
    save_filter_config(db, alice, "ma", {"fast": 20}, enabled=False, thu_tu=0)
    save_filter_config(db, alice, "rsi", {"length": 21, "oversold": 30}, thu_tu=2)
    save_filter_config(db, bob, "rsi", {"length": 7})

    alice_rows = list_filter_configs(db, alice)
    assert [row["filter_name"] for row in alice_rows] == ["ma", "rsi"]
    assert alice_rows[1]["parameters"] == {"length": 21, "oversold": 30}
    assert alice_rows[1]["enabled"] == 1
    assert list_filter_configs(db, bob)[0]["parameters"] == {"length": 7}

    delete_filter_configs(db, alice)
    assert list_filter_configs(db, alice) == []
    assert len(list_filter_configs(db, bob)) == 1


def test_missing_user_rejects_config(db: sqlite3.Connection) -> None:
    with pytest.raises(LookupError):
        save_filter_config(db, 99, "rsi", {})


def test_composite_rules_filter_by_owner(db: sqlite3.Connection) -> None:
    add_composite_rule(db, "Hệ thống", "system", {"logic": "all", "children": []}, "mặc định")
    add_composite_rule(db, "Của Alice", "1", {"logic": "any", "children": [{"filter": "rsi"}]})
    owned = list_composite_rules(db, "1")
    assert len(owned) == 1
    assert owned[0]["definition"]["logic"] == "any"
    assert len(list_composite_rules(db)) == 2


def test_signal_is_unique_per_user_symbol_filter_and_bar(db: sqlite3.Connection) -> None:
    alice = ensure_user(db, "alice")
    bob = ensure_user(db, "bob")
    first_id, created = record_signal(
        db, alice, "fpt", "rsi", "mua", "2026-10-15", {"reason": "dưới 30"}, 100.5
    )
    second_id, again = record_signal(db, alice, "FPT", "rsi", "mua", "2026-10-15", {"reason": "lần 2"})
    other_day, other_created = record_signal(db, alice, "FPT", "rsi", "mua", "2026-10-16")
    bob_id, bob_created = record_signal(db, bob, "FPT", "rsi", "ban", "2026-10-15")

    assert created is True
    assert again is False
    assert first_id == second_id
    assert other_created is True and other_day != first_id
    assert bob_created is True and bob_id != first_id
    assert len(list_signals(db, alice)) == 2
    assert list_signals(db, alice)[0]["details"]["reason"] == "dưới 30"
    assert list_signals(db, alice)[0]["gia_tai_thoi_diem"] == 100.5
    assert list_signals(db, bob)[0]["signal_type"] == "ban"


def test_signal_type_must_be_known(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local")
    with pytest.raises(ValueError):
        record_signal(db, user_id, "FPT", "rsi", "tham_do", "2026-10-15")


def test_market_cache_upserts_same_bar(db: sqlite3.Connection) -> None:
    save_market_bar(db, "fpt", "D", "2026-10-15", 1, 2, 0.5, 1.5, 1000, {"rsi": 28})
    save_market_bar(db, "FPT", "D", "2026-10-15", 1, 3, 0.5, 2.5, 1100, {"rsi": 40})
    bar = get_market_bar(db, "FPT", "D", "2026-10-15")
    assert bar is not None
    assert bar["close"] == 2.5
    assert bar["indicators"] == {"rsi": 40}
    assert get_market_bar(db, "FPT", "D", "2026-10-14") is None


def test_successful_mail_is_unique_for_the_bar(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local")
    signal_id, _ = record_signal(db, user_id, "FPT", "rsi", "mua", "2026-10-15")
    log_notification(
        db, user_id, signal_id, "thành công", "a@example.com", "FPT", "rsi", "2026-10-15"
    )
    assert notification_sent(db, user_id, "FPT", "rsi", "2026-10-15") is True
    with pytest.raises(DuplicateNotification):
        log_notification(
            db, user_id, signal_id, "thành công", "a@example.com", "FPT", "rsi", "2026-10-15"
        )
    log_notification(db, user_id, signal_id, "lỗi", "a@example.com", "FPT", "rsi", "2026-10-14", "smtp")
    assert notification_sent(db, user_id, "FPT", "rsi", "2026-10-14") is False


def test_blank_username_is_rejected(db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        ensure_user(db, "  ")
