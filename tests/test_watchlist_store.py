"""Personal watchlist SQLite store."""

from __future__ import annotations

import pytest

from backend.watchlist_store import (
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    init_watchlist_store,
    list_watchlists,
    normalize_symbols,
    update_watchlist,
)


def test_normalize_symbols_dedupe_upper():
    assert normalize_symbols(["fpt", "FPT", " ssi ", "", "VIC"]) == ["FPT", "SSI", "VIC"]
    assert normalize_symbols('["acb","HPG"]') == ["ACB", "HPG"]


def test_crud_isolated_users(tmp_path):
    db = tmp_path / "market.db"
    init_watchlist_store(db)

    a = create_watchlist("alice", "Core", ["FPT", "SSI"], db_path=db)
    b = create_watchlist("bob", "Banks", ["VCB", "TCB"], db_path=db)
    assert a["id"] != b["id"]
    assert a["symbols"] == ["FPT", "SSI"]

    alice_list = list_watchlists("alice", db_path=db)
    assert len(alice_list) == 1
    assert alice_list[0]["name"] == "Core"
    assert list_watchlists("bob", db_path=db)[0]["symbols"] == ["VCB", "TCB"]

    updated = update_watchlist(
        "alice",
        a["id"],
        name="Core VN",
        symbols=["FPT", "HPG"],
        db_path=db,
    )
    assert updated is not None
    assert updated["name"] == "Core VN"
    assert updated["symbols"] == ["FPT", "HPG"]

    assert get_watchlist("bob", a["id"], db_path=db) is None
    assert delete_watchlist("bob", a["id"], db_path=db) is False
    assert delete_watchlist("alice", a["id"], db_path=db) is True
    assert get_watchlist("alice", a["id"], db_path=db) is None


def test_update_requires_name(tmp_path):
    db = tmp_path / "m.db"
    item = create_watchlist("u1", "A", ["FPT"], db_path=db)
    with pytest.raises(ValueError):
        update_watchlist("u1", item["id"], name="  ", db_path=db)
