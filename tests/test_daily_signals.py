"""iBoard daily signal scan (subset)."""

from __future__ import annotations

from backend.board_universe import symbols_for_market_tab
from backend.daily_signals import ALLOWED_FILTERS, clear_daily_scan_cache, scan_daily_signals


def test_symbols_for_market_tab():
    assert "FPT" in symbols_for_market_tab("VN30")
    assert "SHS" in symbols_for_market_tab("HNX")
    assert symbols_for_market_tab("HOSE") != symbols_for_market_tab("VN30")


def test_scan_daily_signals_monkeypatch(monkeypatch):
    class _Res:
        matched = True
        signal_type = "mua"
        reason = "test"

    def fake_eval(_bars, _params):
        return _Res()

    class _Mod:
        @staticmethod
        def evaluate(bars, params):
            return fake_eval(bars, params)

    monkeypatch.setattr(
        "backend.daily_signals._filter_registry",
        lambda: {"rsi": _Mod()},
    )
    monkeypatch.setattr(
        "backend.daily_signals.load_symbol_bars",
        lambda sym, bars_dir=None: object(),  # truthy non-empty handled below
    )

    import pandas as pd

    monkeypatch.setattr(
        "backend.daily_signals.load_symbol_bars",
        lambda sym, bars_dir=None: pd.DataFrame({"close": [1.0] * 30, "volume": [1.0] * 30}),
    )

    hits, scanned, matched = scan_daily_signals(market="VN30", filter_name="rsi")
    assert scanned >= 1
    assert matched == len(hits)
    assert hits[0]["symbol"] in symbols_for_market_tab("VN30")


def test_allowed_filters_includes_advisor():
    assert "advisor" in ALLOWED_FILTERS
    assert {"candle", "volume", "foreign"} <= ALLOWED_FILTERS
    assert {"bollinger", "adx", "atr", "ma"} <= ALLOWED_FILTERS


def test_scan_daily_signals_cache_same_day(monkeypatch):
    clear_daily_scan_cache()
    calls = {"n": 0}

    class _Res:
        matched = True
        signal_type = "mua"
        reason = "test"

    class _Mod:
        @staticmethod
        def evaluate(bars, params):
            calls["n"] += 1
            return _Res()

    monkeypatch.setattr(
        "backend.daily_signals._filter_registry",
        lambda: {"rsi": _Mod()},
    )
    import pandas as pd

    monkeypatch.setattr(
        "backend.daily_signals.load_symbol_bars",
        lambda sym, bars_dir=None: pd.DataFrame({"close": [1.0] * 30, "volume": [1.0] * 30}),
    )
    hits1, _, _ = scan_daily_signals(market="VN30", filter_name="rsi")
    hits2, _, _ = scan_daily_signals(market="VN30", filter_name="rsi")
    assert hits1 == hits2
    assert calls["n"] >= 1
    clear_daily_scan_cache()
    scan_daily_signals(market="VN30", filter_name="rsi", use_cache=False)
    assert calls["n"] >= 2


def test_scan_advisor_monkeypatch(monkeypatch):
    class _Score:
        total = 72.0
        recommendation = "mua"
        reason = "test advisor"
        pillars = {
            "trend": {"points": 30.0},
            "flow": {"points": 22.0},
            "short_term": {"points": 20.0},
        }

    def fake_compute(_bars, _params):
        return _Score()

    def fake_cfg():
        return {"thresholds": {"buy_min_total": 65, "sell_max_total": 35}}

    monkeypatch.setattr(
        "backend.daily_signals._advisor_engine",
        lambda: (fake_compute, fake_cfg),
    )
    import pandas as pd

    monkeypatch.setattr(
        "backend.daily_signals.load_symbol_bars",
        lambda sym, bars_dir=None: pd.DataFrame({"close": [1.0] * 80, "volume": [1.0] * 80}),
    )

    hits, scanned, matched = scan_daily_signals(market="VN30", filter_name="advisor", buy_min_total=65)
    assert scanned >= 1
    assert matched == len(hits)
    assert hits[0]["total"] == 72.0
    assert hits[0]["filter"] == "advisor"
