"""Unit tests for composite FilterEngine (safe NaN/None coercion)."""

import math

from backend.screener import FilterEngine, annotate_near_limits, build_compose_rules, safe_float


def test_safe_float_handles_none_nan_junk():
    assert safe_float(None) is None
    assert safe_float(float("nan")) is None
    assert safe_float("nan") is None
    assert safe_float("—") is None
    assert safe_float("1,234.5") == 1234.5
    assert safe_float(10) == 10.0


def test_and_volume_and_pct():
    engine = FilterEngine(
        [
            {"field": "volume", "op": "gte", "value": 500_000},
            {"field": "change_pct", "op": "gte", "value": 2},
        ],
        mode="and",
    )
    assert engine.match({"symbol": "FPT", "kind": "equity", "volume": 600_000, "change_pct": 2.5})
    assert not engine.match({"symbol": "FPT", "kind": "equity", "volume": 100, "change_pct": 3})
    assert not engine.match({"symbol": "FPT", "kind": "equity", "volume": 600_000, "change_pct": 1})


def test_or_mode():
    engine = FilterEngine(
        [
            {"field": "change_pct", "op": "gte", "value": 2},
            {"field": "change_pct", "op": "lte", "value": -2},
        ],
        mode="or",
    )
    assert engine.match({"symbol": "A", "kind": "equity", "change_pct": 3})
    assert engine.match({"symbol": "B", "kind": "equity", "change_pct": -3})
    assert not engine.match({"symbol": "C", "kind": "equity", "change_pct": 0.5})


def test_skips_index_by_default():
    engine = FilterEngine([{"field": "volume", "op": "gte", "value": 0}], mode="and")
    assert not engine.match({"symbol": "VNINDEX", "kind": "index", "volume": 9e9})
    assert engine.match({"symbol": "SSI", "kind": "equity", "volume": 1})


def test_missing_numeric_fails_closed():
    engine = FilterEngine([{"field": "change_pct", "op": "gte", "value": 1}])
    assert not engine.match({"symbol": "X", "kind": "equity", "change_pct": None})
    assert not engine.match({"symbol": "X", "kind": "equity", "change_pct": math.nan})


def test_near_ceil_flag():
    rules, mode = build_compose_rules(flags=["ceil"])
    assert mode == "and"
    engine = FilterEngine(rules)
    row = {"symbol": "Y", "kind": "equity", "last": 100, "ceil": 100, "floor": 90}
    annotate_near_limits(row)
    assert row["_near_ceil"] == 1
    assert engine.match({"symbol": "Y", "kind": "equity", "last": 100, "ceil": 100, "floor": 90})
    assert not engine.match({"symbol": "Y", "kind": "equity", "last": 99, "ceil": 100, "floor": 90})


def test_filter_rows_count():
    engine = FilterEngine([{"field": "volume", "op": "gte", "value": 1_000_000}])
    rows = [
        {"symbol": "A", "kind": "equity", "volume": 2_000_000},
        {"symbol": "B", "kind": "equity", "volume": 10},
        {"symbol": "VN30", "kind": "index", "volume": 9e9},
    ]
    out = engine.filter_rows(rows)
    assert [r["symbol"] for r in out] == ["A"]


def test_invalid_rules_ignored():
    engine = FilterEngine([{"field": "volume", "op": "nope", "value": 1}, {"field": "volume", "op": "gte", "value": 5}])
    assert len(engine.rules) == 1
    assert engine.match({"symbol": "Z", "kind": "equity", "volume": 10})
