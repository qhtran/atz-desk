"""Engine ghi history khi khớp và không nhân đôi cùng user, mã, filter, ngày nến."""

from __future__ import annotations

import sqlite3

from engine.runner import run_frames
from storage.repository import ensure_user, get_market_bar, list_signals, save_filter_config
from tests.bars import frame


def test_matching_bar_is_stored_once(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local")
    save_filter_config(db, user_id, "ma", {"fast": 2, "slow": 4})
    bars = frame([1, 1, 1, 1, 1, 3])
    first = run_frames(db, user_id, {"fpt": bars})
    second = run_frames(db, user_id, {"fpt": bars})

    hits = [row for row in first if row["matched"]]
    assert len(hits) == 1
    assert hits[0]["created"] is True
    assert hits[0]["signal_type"] == "mua"
    assert [row["created"] for row in second if row["matched"]] == [False]
    assert len(list_signals(db, user_id)) == 1
    assert get_market_bar(db, "FPT", "D", hits[0]["bar_date"]) is not None


def test_a_miss_does_not_write_history(db: sqlite3.Connection) -> None:
    user_id = ensure_user(db, "local")
    save_filter_config(db, user_id, "ma", {"fast": 2, "slow": 4})
    run_frames(db, user_id, {"fpt": frame([1, 2, 3])})
    assert list_signals(db, user_id) == []


def test_another_user_gets_a_separate_row(db: sqlite3.Connection) -> None:
    alice = ensure_user(db, "alice")
    bob = ensure_user(db, "bob")
    save_filter_config(db, alice, "ma", {"fast": 2, "slow": 4})
    save_filter_config(db, bob, "ma", {"fast": 2, "slow": 4})
    bars = frame([1, 1, 1, 1, 1, 3])
    run_frames(db, alice, {"FPT": bars})
    run_frames(db, bob, {"FPT": bars})
    assert len(list_signals(db, alice)) == 1
    assert len(list_signals(db, bob)) == 1
