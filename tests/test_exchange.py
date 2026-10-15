"""Import file của user A vào user B không đụng dữ liệu của A."""

from __future__ import annotations

import sqlite3

import pytest

from engine.exchange import export_user, import_user
from storage.repository import (
    add_composite_rule,
    ensure_user,
    list_composite_rules,
    list_filter_configs,
    save_filter_config,
    set_user_settings,
)


def test_import_into_another_user_leaves_the_source_unchanged(db: sqlite3.Connection) -> None:
    alice = ensure_user(db, "alice", "a@example.com")
    bob = ensure_user(db, "bob", "b@example.com")
    save_filter_config(db, alice, "rsi", {"length": 14}, thu_tu=0)
    add_composite_rule(db, "Flow A", str(alice), {"logic": "all", "children": []})
    set_user_settings(db, alice, {"email_bat": True}, "a@example.com")

    payload = export_user(db, alice)
    import_user(db, bob, payload, replace=True)

    assert list_filter_configs(db, alice)[0]["parameters"] == {"length": 14}
    assert list_composite_rules(db, str(alice))[0]["name"] == "Flow A"
    assert list_filter_configs(db, bob)[0]["filter_name"] == "rsi"
    assert list_composite_rules(db, str(bob))[0]["owner"] == str(bob)
    assert export_user(db, bob)["username"] == "bob"


def test_unknown_version_changes_nothing(db: sqlite3.Connection) -> None:
    alice = ensure_user(db, "alice")
    save_filter_config(db, alice, "ma", {"fast": 10, "slow": 20})
    with pytest.raises(ValueError):
        import_user(db, alice, {"version": 9, "filters": []}, replace=True)
    assert len(list_filter_configs(db, alice)) == 1


def test_replace_drops_filters_missing_from_the_file(db: sqlite3.Connection) -> None:
    alice = ensure_user(db, "alice")
    save_filter_config(db, alice, "ma", {"fast": 10, "slow": 20})
    save_filter_config(db, alice, "rsi", {"length": 14})
    payload = export_user(db, alice)
    payload["filters"] = [item for item in payload["filters"] if item["filter_name"] == "rsi"]
    import_user(db, alice, payload, replace=True)
    names = [row["filter_name"] for row in list_filter_configs(db, alice)]
    assert names == ["rsi"]
