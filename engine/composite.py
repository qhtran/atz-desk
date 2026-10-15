"""Ghép filter cơ bản bằng all, any hoặc weighted, kèm điều kiện VNINDEX."""

from __future__ import annotations

from types import ModuleType

import pandas as pd

from analysis.technical import sma
from filters.base import SignalResult, hit, hold, waiting


def _index_ready(index_bars: pd.DataFrame | None, length: int) -> tuple[bool, str]:
    if index_bars is None or "close" not in getattr(index_bars, "columns", []):
        return False, "không đủ dữ liệu"
    if len(index_bars) < length:
        return False, "không đủ dữ liệu"
    close = pd.to_numeric(index_bars["close"], errors="coerce")
    average = sma(close, length)
    if pd.isna(average.iloc[-1]) or pd.isna(close.iloc[-1]):
        return False, "không đủ dữ liệu"
    if float(close.iloc[-1]) > float(average.iloc[-1]):
        return True, ""
    return False, "VNINDEX dưới MA"


def evaluate_composite(
    definition: dict,
    bars: pd.DataFrame,
    index_bars: pd.DataFrame | None = None,
    modules: dict[str, ModuleType] | None = None,
) -> SignalResult:
    """Trả một tín hiệu. Thiếu dữ liệu hoàn cảnh thì không khớp và không ném lỗi."""
    context = definition.get("context") or {}
    if context.get("index_above_ma"):
        ready, reason = _index_ready(index_bars, int(context["index_above_ma"]))
        if not ready:
            return waiting(reason)

    logic = definition.get("logic", "all")
    if logic not in {"all", "any", "weighted"}:
        return waiting("logic không hỗ trợ")
    if modules is None:
        from filters import load_registry

        modules = load_registry()

    children = definition.get("children") or []
    if not children:
        return waiting("không có filter con")
    results: list[tuple[float, SignalResult]] = []
    for child in children:
        name = child.get("filter")
        module = modules.get(name)
        if module is None:
            return waiting(f"không có filter {name}")
        results.append((float(child.get("weight", 1)), module.evaluate(bars, child.get("params") or {})))

    if logic == "all":
        return _all(results)
    if logic == "any":
        return _any(results)
    return _weighted(results, float(definition.get("min_weight", 1)))


def _all(results: list[tuple[float, SignalResult]]) -> SignalResult:
    matched = [item for _weight, item in results if item.matched]
    if len(matched) != len(results):
        return hold("chưa đủ filter con")
    kinds = {item.signal_type for item in matched}
    if len(kinds) != 1:
        return hold("các filter con không cùng chiều")
    kind = kinds.pop()
    return hit(kind, "mọi filter con cùng chiều", {"signals": [item.signal_type for item in matched]})


def _any(results: list[tuple[float, SignalResult]]) -> SignalResult:
    matched = [item for _weight, item in results if item.matched]
    if not matched:
        return hold("không filter con nào khớp")
    kinds = {item.signal_type for item in matched}
    if len(kinds) != 1:
        return hold("các filter khớp không cùng chiều")
    kind = kinds.pop()
    return hit(kind, matched[0].reason, {"signals": [item.signal_type for item in matched]})


def _weighted(results: list[tuple[float, SignalResult]], min_weight: float) -> SignalResult:
    total = sum(weight for weight, _item in results)
    if total <= 0:
        return waiting("không đủ dữ liệu")
    scores: dict[str, float] = {}
    for weight, item in results:
        if item.matched:
            scores[item.signal_type] = scores.get(item.signal_type, 0.0) + weight
    if not scores:
        return hold("trọng số chưa đạt")
    best = max(scores.values())
    leaders = [kind for kind, score in scores.items() if score == best]
    if len(leaders) != 1 or best < min_weight:
        return hold("trọng số chưa đạt")
    return hit(leaders[0], "đủ trọng số", {"score": best, "total": total})
