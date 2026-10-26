"""API phân tích mã — bars + marker filter."""

from __future__ import annotations

import pandas as pd

from backend.symbol_analysis import chart_limit_from_query, load_bars_for_chart, scan_filter_markers


def test_chart_limit_from_query_range_presets():
    assert chart_limit_from_query(range_key="1m") == 22
    assert chart_limit_from_query(range_key="5y") == 1260
    assert chart_limit_from_query(limit=9999) == 1300


def test_load_bars_for_chart_from_csv(monkeypatch, tmp_path):
    path = tmp_path / "FPT.csv"
    path.write_text(
        "time,open,high,low,close,volume\n"
        "2026-01-01,10,11,9,10.5,1000\n"
        "2026-01-02,10.5,11,10,10.8,1100\n",
        encoding="utf-8",
    )

    def fake_load(sym, bars_dir=None):
        if sym == "FPT":
            return pd.read_csv(path)
        return None

    monkeypatch.setattr("backend.symbol_analysis.load_symbol_bars", fake_load)
    rows = load_bars_for_chart("FPT", limit=10)
    assert len(rows) == 2
    assert rows[-1]["close"] == 10.8


def test_scan_filter_markers_edge_on_rising_match(monkeypatch):
    closes = [float(i) for i in range(1, 41)]

    def fake_bars(sym, bars_dir=None):
        if sym != "X":
            return None
        return pd.DataFrame(
            {
                "time": [f"2026-01-{d:02d}" for d in range(1, len(closes) + 1)],
                "open": closes,
                "high": [c + 0.5 for c in closes],
                "low": [c - 0.5 for c in closes],
                "close": closes,
                "volume": [1000.0] * len(closes),
            }
        )

    class _Res:
        def __init__(self, matched: bool, signal_type: str = "mua"):
            self.matched = matched
            self.signal_type = signal_type
            self.reason = "test"

    def fake_eval(bars, _params):
        last = float(bars["close"].iloc[-1])
        return _Res(last >= 35)

    class _Mod:
        @staticmethod
        def evaluate(bars, params):
            return fake_eval(bars, params)

    monkeypatch.setattr("backend.symbol_analysis.load_symbol_bars", fake_bars)
    monkeypatch.setattr("backend.symbol_analysis._filter_registry", lambda: {"demo": _Mod()})
    monkeypatch.setattr("backend.symbol_analysis.ALLOWED_FILTERS", frozenset({"demo"}))

    out = scan_filter_markers("X", "demo", limit=40)
    assert out["ok"] is True
    assert out["last"]["matched"] is True
    assert len(out["markers"]) >= 1
    assert out["markers"][0]["signal_type"] == "mua"
