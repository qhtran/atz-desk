"""Logic composite và điều kiện VNINDEX. Thiếu dữ liệu thì không ném lỗi."""

from __future__ import annotations

import pandas as pd

from engine.composite import evaluate_composite
from filters.base import SignalResult


class _Stub:
    def __init__(self, result: SignalResult) -> None:
        self.result = result

    def evaluate(self, bars, params=None):
        del bars, params
        return self.result


def _buy() -> SignalResult:
    return SignalResult(True, "mua", 1.0, "mua", {})


def _sell() -> SignalResult:
    return SignalResult(True, "ban", 1.0, "ban", {})


def _miss() -> SignalResult:
    return SignalResult(False, "giu", None, "không", {})


def test_all_matches_only_when_every_child_agrees() -> None:
    modules = {"a": _Stub(_buy()), "b": _Stub(_buy())}
    definition = {"logic": "all", "children": [{"filter": "a"}, {"filter": "b"}]}
    result = evaluate_composite(definition, pd.DataFrame(), modules=modules)
    assert result.matched is True
    assert result.signal_type == "mua"

    modules["b"] = _Stub(_miss())
    missed = evaluate_composite(definition, pd.DataFrame(), modules=modules)
    assert missed.matched is False


def test_any_rejects_opposite_signals() -> None:
    modules = {"a": _Stub(_buy()), "b": _Stub(_sell())}
    definition = {"logic": "any", "children": [{"filter": "a"}, {"filter": "b"}]}
    result = evaluate_composite(definition, pd.DataFrame(), modules=modules)
    assert result.matched is False


def test_weighted_needs_the_minimum_score() -> None:
    modules = {"a": _Stub(_buy()), "b": _Stub(_miss())}
    definition = {
        "logic": "weighted",
        "min_weight": 2,
        "children": [{"filter": "a", "weight": 1}, {"filter": "b", "weight": 1}],
    }
    short = evaluate_composite(definition, pd.DataFrame(), modules=modules)
    assert short.matched is False
    definition["min_weight"] = 1
    reached = evaluate_composite(definition, pd.DataFrame(), modules=modules)
    assert reached.matched is True
    assert reached.signal_type == "mua"


def test_missing_index_does_not_raise() -> None:
    definition = {
        "logic": "all",
        "children": [{"filter": "a"}],
        "context": {"index_above_ma": 20},
    }
    result = evaluate_composite(definition, pd.DataFrame(), index_bars=None, modules={"a": _Stub(_buy())})
    assert result.matched is False
    assert result.reason == "không đủ dữ liệu"
    assert result.signal_type == "cho"


def test_index_below_ma_blocks_the_rule() -> None:
    index = pd.DataFrame({"close": [5, 4, 3, 2, 1]})
    definition = {"logic": "all", "children": [{"filter": "a"}], "context": {"index_above_ma": 3}}
    result = evaluate_composite(definition, pd.DataFrame(), index, {"a": _Stub(_buy())})
    assert result.matched is False
    assert result.reason == "VNINDEX dưới MA"


def test_index_above_ma_runs_children() -> None:
    index = pd.DataFrame({"close": [1, 2, 3, 4, 5]})
    definition = {"logic": "all", "children": [{"filter": "a"}], "context": {"index_above_ma": 3}}
    result = evaluate_composite(definition, pd.DataFrame(), index, {"a": _Stub(_buy())})
    assert result.matched is True
    assert result.signal_type == "mua"
