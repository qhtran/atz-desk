"""Registry phải thấy filter nhờ quét file, không nhờ danh sách cứng."""

from __future__ import annotations

from filters import load_registry
from filters.base import FilterSpec, SignalResult


def test_package_registry_lists_the_six_filters() -> None:
    found = load_registry()
    assert set(found) == {
        "ma", "rsi", "macd", "bollinger", "volume", "candle", "foreign", "proprietary",
        "ichimoku", "mcdx", "adx", "atr", "advisor",
        "rs_index", "breakout_52w", "stochastic",
        "foreign_streak", "liquidity", "market_regime",
    }


def test_registry_loads_a_new_file(tmp_path) -> None:
    (tmp_path / "demo.py").write_text(
        """
from filters.base import FilterSpec, SignalResult

FILTER = FilterSpec("demo", "Demo", "thử", "test", ())

def evaluate(bars, params=None):
    return SignalResult(False, "cho", None, "demo", {})
""",
        encoding="utf-8",
    )
    found = load_registry(tmp_path)
    assert set(found) == {"demo"}
    assert found["demo"].evaluate(None).reason == "demo"
