"""Phase C — F3 themes loader + alert batch (API helpers)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.portfolio_f3 import (
    batch_f3_alerts,
    combine_f3_intraday_alert,
    load_f3_sector_themes,
)


def test_load_f3_themes_from_repo_config():
    themes = load_f3_sector_themes()
    assert len(themes) >= 10
    assert any("Chứng" in t["name"] for t in themes)


def test_combine_f3_intraday_order():
    assert combine_f3_intraday_alert("xu hướng ngày: tăng", "+5%") == "xu hướng ngày: tăng · +5%"
    assert combine_f3_intraday_alert("—", "+5%") == "+5%"
    assert combine_f3_intraday_alert("xu hướng ngày: sideway", "—") == "xu hướng ngày: sideway"


def test_batch_f3_alerts_monkeypatch(monkeypatch):
    def fake(sym: str, **kwargs):
        return f"f3-{sym}"

    monkeypatch.setattr("backend.portfolio_f3.f3_alert_for_symbol", fake)
    out = batch_f3_alerts(["fpt", "FPT", "VIC"])
    assert list(out.keys()) == ["FPT", "VIC"]
    assert out["FPT"] == "f3-FPT"


def test_f3_alert_missing_bars(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OHLCV_BARS_DIR", str(tmp_path))
    from backend import portfolio_f3 as pf3

    pf3.OHLCV_DIR = tmp_path
    pf3._f3_cache.clear()
    pf3._alert_column_fn.cache_clear()
    text = pf3.f3_alert_for_symbol("NOFILE", use_cache=False)
    assert text == "—"
