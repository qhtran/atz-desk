"""iBoard daily signal scan (subset)."""

from __future__ import annotations

from backend.board_universe import symbols_for_market_tab
from backend.daily_signals import ALLOWED_FILTERS, clear_daily_scan_cache, scan_daily_signals


def test_symbols_for_market_tab():
    assert "FPT" in symbols_for_market_tab("VN30")
    assert "SHS" in symbols_for_market_tab("HNX")
    assert symbols_for_market_tab("HOSE") != symbols_for_market_tab("VN30")


def test_scan_daily_signals_monkeypatch(monkeypatch):
    from backend.filters._types import BatchSignal

    import pandas as pd

    def fake_rsi_batch(panels, params=None):
        return {sym: BatchSignal(True, "mua", "test", None) for sym in panels}

    import backend.filters as bf

    monkeypatch.setitem(bf.BATCH_EVALUATORS, "rsi", fake_rsi_batch)
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
    assert {
        "bollinger",
        "adx",
        "atr",
        "ma",
        "rs_index",
        "breakout_52w",
        "stochastic",
        "foreign_streak",
        "liquidity",
        "market_regime",
    } <= ALLOWED_FILTERS


def test_scan_daily_signals_multi_and(monkeypatch):
    clear_daily_scan_cache()
    calls = {"rsi": 0, "ma": 0}

    class _Res:
        matched = True
        signal_type = "mua"
        reason = "ok"

    def make_mod(name):
        class _Mod:
            @staticmethod
            def evaluate(_bars, _params):
                calls[name] += 1
                return _Res()

        return _Mod()

    from backend.filters._types import BatchSignal
    import backend.filters as bf

    def fake_rsi_batch(panels, params=None):
        calls["rsi"] += 1
        return {sym: BatchSignal(True, "mua", "ok", None) for sym in panels}

    def fake_ma_batch(panels, params=None):
        calls["ma"] += 1
        return {sym: BatchSignal(True, "mua", "ok", None) for sym in panels}

    monkeypatch.setitem(bf.BATCH_EVALUATORS, "rsi", fake_rsi_batch)
    monkeypatch.setitem(bf.BATCH_EVALUATORS, "ma", fake_ma_batch)
    import pandas as pd

    monkeypatch.setattr(
        "backend.daily_signals.load_symbol_bars",
        lambda sym, bars_dir=None: pd.DataFrame(
            {"close": [1.0] * 30, "high": [2.0] * 30, "low": [0.5] * 30, "open": [1.0] * 30, "volume": [1.0] * 30}
        ),
    )
    hits, scanned, matched = scan_daily_signals(
        market="VN30", filters=["rsi", "ma"], combine="and", use_cache=False
    )
    assert scanned >= 1
    assert matched == len(hits)
    assert calls["rsi"] >= 1 and calls["ma"] >= 1
    assert hits[0]["filters"] == ["rsi", "ma"]


def test_scan_daily_signals_cache_same_day(monkeypatch):
    clear_daily_scan_cache()
    calls = {"n": 0}

    from backend.filters._types import BatchSignal
    import backend.filters as bf

    def fake_rsi_batch(panels, params=None):
        calls["n"] += 1
        return {sym: BatchSignal(True, "mua", "test", None) for sym in panels}

    monkeypatch.setitem(bf.BATCH_EVALUATORS, "rsi", fake_rsi_batch)
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


def test_native_bollinger_matches_legacy():
    from backend.filters.bollinger_batch import evaluate_bollinger_batch
    from backend.portfolio_f3 import _ensure_legacy_path
    from tests.bars import frame

    _ensure_legacy_path()
    from filters.bollinger import evaluate as legacy_bollinger

    import pandas as pd

    samples = {
        "AAA": frame([10.0 - i * 0.5 for i in range(25)]),
        "BBB": frame([20.0 + i * 0.3 for i in range(25)]),
        "CCC": frame([5.0] * 25),
    }
    batch = evaluate_bollinger_batch(samples)
    for sym, bars in samples.items():
        leg = legacy_bollinger(bars)
        bat = batch[sym]
        assert bat.matched == leg.matched
        assert bat.signal_type == leg.signal_type
        assert bat.reason == leg.reason


def test_native_ma_matches_legacy():
    from backend.filters.ma_batch import evaluate_ma_batch
    from backend.portfolio_f3 import _ensure_legacy_path
    from tests.bars import frame

    _ensure_legacy_path()
    from filters.ma import evaluate as legacy_ma

    params = {"fast": 2, "slow": 4}
    samples = {
        "UP": frame([1, 1, 1, 1, 1, 3]),
        "DOWN": frame([5, 5, 5, 5, 5, 1]),
        "SHORT": frame([1, 2, 3]),
    }
    batch = evaluate_ma_batch(samples, params)
    for sym, bars in samples.items():
        leg = legacy_ma(bars, params)
        bat = batch[sym]
        assert bat.matched == leg.matched, sym
        assert bat.signal_type == leg.signal_type, sym
        assert bat.reason == leg.reason, sym


def test_native_ma_periods_10_20_cross():
    from backend.filters.ma_batch import evaluate_ma_batch
    from tests.bars import frame

    closes = [float(i) for i in range(1, 25)] + [30.0, 35.0]
    samples = {"TREND": frame(closes)}
    batch = evaluate_ma_batch(samples, {"fast": 10, "slow": 20, "ma_type": "sma"})
    assert "TREND" in batch
    assert batch["TREND"].signal_type in {"mua", "ban", "giu"}


def test_native_volume_matches_legacy():
    from backend.filters.volume_batch import evaluate_volume_batch
    from backend.portfolio_f3 import _ensure_legacy_path
    from tests.bars import frame

    _ensure_legacy_path()
    from filters.volume import evaluate as legacy_volume

    params = {"length": 20, "spike": 1.5}
    samples = {
        "BUY": frame(
            [10.0] * 20 + [12.0],
            [100.0] * 20 + [1000.0],
            [10.0] * 20 + [11.0],
        ),
        "SELL": frame(
            [10.0] * 20 + [8.0],
            [100.0] * 20 + [1000.0],
            [10.0] * 20 + [11.0],
        ),
        "QUIET": frame([10.0] * 21),
    }
    batch = evaluate_volume_batch(samples, params)
    for sym, bars in samples.items():
        leg = legacy_volume(bars, params)
        bat = batch[sym]
        assert bat.matched == leg.matched, sym
        assert bat.signal_type == leg.signal_type, sym
        assert bat.reason == leg.reason, sym


def test_native_rsi_co_ban_matches_legacy():
    from backend.filters.rsi_batch import evaluate_rsi_batch
    from backend.portfolio_f3 import _ensure_legacy_path
    from tests.bars import frame

    _ensure_legacy_path()
    from filters.rsi import evaluate as legacy_rsi

    params = {"mode": "co_ban", "length": 14, "oversold": 30, "overbought": 70}
    samples = {
        "DOWN": frame([100 - i for i in range(20)]),
        "UP": frame([50 + i for i in range(20)]),
        "FLAT": frame([10.0] * 20),
    }
    batch = evaluate_rsi_batch(samples, params)
    for sym, bars in samples.items():
        leg = legacy_rsi(bars, params)
        bat = batch[sym]
        assert bat.matched == leg.matched, sym
        assert bat.signal_type == leg.signal_type, sym
        assert bat.reason == leg.reason, sym
