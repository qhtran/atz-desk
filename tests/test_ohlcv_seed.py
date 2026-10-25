from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from backend import ohlcv_seed


def test_parse_markets_all_and_single():
    assert ohlcv_seed.parse_markets("ALL") == list(ohlcv_seed.MARKET_TABS)
    assert ohlcv_seed.parse_markets("vn30") == ["VN30"]


def test_parse_markets_invalid():
    with pytest.raises(ValueError):
        ohlcv_seed.parse_markets("FOREIGN")


def test_collect_symbols_union_no_dup():
    syms = ohlcv_seed.collect_symbols(["HOSE", "VN30"])
    assert syms == sorted(set(syms))
    assert "VIC" in syms
    assert len(syms) >= len(ohlcv_seed.collect_symbols(["VN30"]))


def test_seed_symbols_dry_run():
    rows = ohlcv_seed.seed_symbols(["AAA", "BBB"], dry_run=True)
    assert len(rows) == 2
    assert all(r.ok and r.skipped for r in rows)
    summary = ohlcv_seed.summarize(rows)
    assert summary["dry_run"] is True
    assert summary["fail"] == 0


def test_count_cached_symbols(tmp_path: Path):
    (tmp_path / "AAA.csv").write_text("time,close\n2026-01-01,1\n", encoding="utf-8")
    assert ohlcv_seed.count_cached_symbols(["AAA", "BBB"], tmp_path) == 1


def test_seed_symbols_calls_loader(monkeypatch):
    calls: list[str] = []

    def fake_load_bars(symbol: str, start: str):
        calls.append(f"{symbol}:{start}")
        return object()

    monkeypatch.setattr(ohlcv_seed, "_ensure_legacy_path", lambda: None)

    import sys

    fake_config = type(sys)("config")
    fake_config.CHART_DAYS = 30
    fake_client = type(sys)("datasource.client")
    fake_client.load_bars = fake_load_bars
    monkeypatch.setitem(sys.modules, "config", fake_config)
    monkeypatch.setitem(sys.modules, "datasource.client", fake_client)

    rows = ohlcv_seed.seed_symbols(["ZZZ"], sleep_seconds=0, dry_run=False)
    assert len(rows) == 1 and rows[0].ok
    assert calls == ["ZZZ:" + (date.today() - timedelta(days=30)).isoformat()]
