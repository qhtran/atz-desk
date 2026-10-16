"""Lọc bảng Realtime + cache spark URI."""

from __future__ import annotations

import pandas as pd

from ui_realtime.board_view import cached_spark_uri, filter_by_symbol, pick_quote_row, spark_cache_key


def test_filter_by_symbol():
    frame = pd.DataFrame({"Mã": ["VIC", "FPT", "VNM"], "Giá": [1, 2, 3]})
    assert filter_by_symbol(frame, "v").iloc[0]["Mã"] == "VIC"
    assert list(filter_by_symbol(frame, "FP")["Mã"]) == ["FPT"]
    assert len(filter_by_symbol(frame, "")) == 3


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
