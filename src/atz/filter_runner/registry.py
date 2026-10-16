"""Filter Registry: plugin trong filters/ (load_registry của app) + composite rule của user."""
from __future__ import annotations

from engine.composite import evaluate_composite
from filters import load_registry


class FilterRegistry:
    def __init__(self, modules=None):
        self.modules = modules if modules is not None else load_registry()

    def names(self) -> list[str]:
        return sorted(self.modules)

    def job(self, item: dict, index_bars):
        """item: {"kind": "filter"|"composite", "name", "params"|"definition"} -> callable(bars) hoặc None."""
        if item["kind"] == "composite":
            definition, modules = item["definition"], self.modules
            return lambda bars: evaluate_composite(definition, bars, index_bars, modules)
        module = self.modules.get(item["name"])
        if module is None:
            return None
        params = item.get("params") or {}
        return lambda bars: module.evaluate(bars, params)
