"""Phase D portfolio SQLite store."""

from __future__ import annotations

from backend.portfolio_store import list_positions, migrate_if_empty, replace_positions


def test_replace_and_list_isolated_users(tmp_path):
    db = tmp_path / "p.db"
    replace_positions(
        "alice",
        [{"symbol": "FPT", "qty": 100, "avg": 90000}],
        db_path=db,
    )
    replace_positions(
        "bob",
        [{"symbol": "VIC", "qty": 200, "avg": 45000}],
        db_path=db,
    )
    assert len(list_positions("alice", db_path=db)) == 1
    assert list_positions("alice", db_path=db)[0]["symbol"] == "FPT"
    assert list_positions("bob", db_path=db)[0]["symbol"] == "VIC"


def test_migrate_if_empty_once(tmp_path):
    db = tmp_path / "p.db"
    migrated, rows = migrate_if_empty(
        "u1",
        [{"symbol": "HPG", "qty": 50, "avg": 25000}],
        db_path=db,
    )
    assert migrated is True
    assert rows[0]["symbol"] == "HPG"
    migrated2, rows2 = migrate_if_empty(
        "u1",
        [{"symbol": "ZZZ", "qty": 1, "avg": 1}],
        db_path=db,
    )
    assert migrated2 is False
    assert rows2[0]["symbol"] == "HPG"
