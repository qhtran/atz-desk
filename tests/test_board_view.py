"""Lọc bảng Realtime + cache spark URI."""

from __future__ import annotations

import pandas as pd

from ui_realtime.board_view import (
    cached_spark_uri,
    detect_price_flashes,
    filter_by_symbol,
    mark_pinned_column,
    merge_flash_hold,
    normalize_pins,
    pick_quote_row,
    sort_pinned_first,
    spark_cache_key,
)


def test_filter_by_symbol():
    frame = pd.DataFrame({"Mã": ["VIC", "FPT", "VNM"], "Giá": [1, 2, 3]})
    assert filter_by_symbol(frame, "v").iloc[0]["Mã"] == "VIC"
    assert list(filter_by_symbol(frame, "FP")["Mã"]) == ["FPT"]
    assert len(filter_by_symbol(frame, "")) == 3


def test_sort_pinned_first_and_mark():
    frame = pd.DataFrame({"Mã": ["VIC", "FPT", "VNM", "AAA"], "Giá": [1, 2, 3, 4]})
    ordered = sort_pinned_first(frame, ["vnm", "fpt", "fpt", "ZZZ"])
    assert list(ordered["Mã"]) == ["VNM", "FPT", "VIC", "AAA"]
    marked = mark_pinned_column(ordered, ["FPT", "VNM"])
    assert list(marked["Ghim"]) == ["★", "★", "", ""]
    assert normalize_pins(["a", "A", "", "b"]) == ["A", "B"]


def test_spark_cache_hits_builder_once():
    cache: dict = {}
    calls = {"n": 0}

    def build():
        calls["n"] += 1
        return "uri-1"

    a = cached_spark_uri(
        cache, code="AAA", spark=[1.0, 2.0], change=1.0, state="up", price=20000, builder=build
    )
    b = cached_spark_uri(
        cache, code="AAA", spark=[1.0, 2.0], change=1.0, state="up", price=20000, builder=build
    )
    assert a == b == "uri-1" and calls["n"] == 1
    cached_spark_uri(
        cache, code="AAA", spark=[1.0, 2.5], change=1.0, state="up", price=20000, builder=build
    )
    assert calls["n"] == 2
    assert spark_cache_key("aaa", "up", 20000.4, [1.0, 2.0])[0] == "AAA"


def test_pick_quote_row():
    rows = [{"Mã": "VIC", "Giá": 1}, {"Mã": "FPT", "Giá": 2}]
    assert pick_quote_row(rows, "fpt")["Giá"] == 2
    assert pick_quote_row(rows, "") is None


def test_detect_price_flashes_min_tick():
    prev = {"AAA": 10000.0, "BBB": 20000.0}
    nxt = {"AAA": 10040.0, "BBB": 20020.0}  # BBB < 50 VND
    got = detect_price_flashes(prev, nxt, min_tick=50)
    assert got == {"AAA": True}
    assert detect_price_flashes(prev, {"AAA": 9900.0}, min_tick=50) == {"AAA": False}


def test_merge_flash_hold_lingers():
    visible, hold = merge_flash_hold({"FPT": True}, {}, hold_cycles=2)
    assert visible == {"FPT": True} and hold["FPT"]["left"] == 1
    visible2, hold2 = merge_flash_hold({}, hold, hold_cycles=2)
    assert visible2 == {"FPT": True} and "FPT" not in hold2
