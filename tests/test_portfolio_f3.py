"""F3 themes, native daily alerts, and accordion markup."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.f3_indicators import alert_column_for_bars, load_f3_alert_config
from backend.portfolio_f3 import (
    batch_f3_alerts,
    combine_f3_intraday_alert,
    load_f3_sector_themes,
)

ROOT = Path(__file__).resolve().parents[1]


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


def _bars(closes: list[float], *, high_pad: float = 0.2, low_pad: float = 0.2) -> pd.DataFrame:
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "time": f"2026-01-{(index % 28) + 1:02d}",
                "open": close,
                "high": close + high_pad,
                "low": close - low_pad,
                "close": close,
                "volume": 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def test_f3_alert_missing_bars(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OHLCV_BARS_DIR", str(tmp_path))
    from backend import portfolio_f3 as pf3

    pf3.OHLCV_DIR = tmp_path
    pf3._f3_cache.clear()
    text = pf3.f3_alert_for_symbol("NOFILE", use_cache=False)
    assert text == "—"


def test_portfolio_f3_alerts_are_native():
    source = (ROOT / "backend" / "portfolio_f3.py").read_text(encoding="utf-8")
    assert "analysis.f3_alerts" not in source
    assert "f3_indicators" in source


def test_load_f3_alert_config_from_repo():
    cfg = load_f3_alert_config(ROOT / "config" / "f3_alerts.yaml")
    assert cfg["ma_periods"] == [20, 50, 100, 200]
    assert cfg["bollinger"]["period"] == 20
    assert cfg["ichimoku"]["displacement"] == 26
    assert cfg["swing"]["near_pct"] == 1.5


def test_alert_config_missing_file_uses_defaults(tmp_path: Path):
    cfg = load_f3_alert_config(tmp_path / "missing.yaml")
    assert cfg["min_bars"] == 20
    assert 200 in cfg["ma_periods"]


def test_flat_series_is_bb_mid():
    text = alert_column_for_bars("FPT", _bars([20.0] * 30, high_pad=0.0, low_pad=0.0))
    assert text == "BB giữa"


def test_price_above_ma50():
    closes = [10.0] * 40 + [float(20 + i) for i in range(20)]
    text = alert_column_for_bars("VCB", _bars(closes))
    assert "Giá trên MA50" in text


def test_uptrend_mentions_ichimoku_cloud():
    closes = [float(i + 1) for i in range(90)]
    text = alert_column_for_bars("HPG", _bars(closes, high_pad=0.2, low_pad=0.2))
    assert "trên mây Ichimoku" in text or "TK cắt" in text


def test_near_resistance_uses_vnd():
    # Pivot high 98.5 (nghìn đồng) with the last close within 1.5%.
    n = 40
    highs = [90.0] * n
    lows = [89.0] * n
    closes = [90.0] * n
    highs[20] = 98.5
    lows[20] = 90.0
    closes[-1] = 97.5
    highs[-1] = 97.8
    lows[-1] = 97.0
    bars = pd.DataFrame(
        {
            "time": [f"2026-03-{(index % 28) + 1:02d}" for index in range(n)],
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1_000_000] * n,
        }
    )
    text = alert_column_for_bars("SSI", bars)
    assert "gần kháng cự 98,500" in text


def test_short_history_is_dash():
    assert alert_column_for_bars("SSI", _bars([10.0] * 10)) == "—"


def test_session_date_drops_later_bars():
    bars = _bars([20.0] * 30, high_pad=0.0, low_pad=0.0)
    bars["time"] = ["2026-11-01"] * len(bars)
    assert alert_column_for_bars("SSI", bars, session_date=date(2026, 10, 1)) == "—"


def test_f3_alert_cache_per_session(tmp_path: Path, monkeypatch):
    from backend import portfolio_f3 as pf3

    (tmp_path / "VCB.csv").write_text(
        "time,open,high,low,close,volume\n2026-01-01,1,1,1,1,1\n",
        encoding="utf-8",
    )
    calls = {"n": 0}

    def fake(symbol, bars, **kwargs):
        calls["n"] += 1
        return f"native-{symbol}"

    monkeypatch.setattr(pf3, "alert_column_for_bars", fake)
    pf3.OHLCV_DIR = tmp_path
    pf3._f3_cache.clear()
    day = date(2026, 10, 29)
    assert pf3.f3_alert_for_symbol("VCB", session_date=day) == "native-VCB"
    assert pf3.f3_alert_for_symbol("vcb", session_date=day) == "native-VCB"
    assert calls["n"] == 1
    assert pf3.f3_alert_for_symbol("VCB", session_date=date(2026, 10, 30)) == "native-VCB"
    assert calls["n"] == 2


def test_alerts_endpoint_keeps_ok_contract(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr(
        "backend.main.batch_f3_alerts",
        lambda symbols: {sym: "Giá trên MA50" for sym in symbols},
    )
    client = TestClient(app)
    response = client.post("/api/portfolio/alerts", json={"symbols": ["vcb", "VCB", "HPG"]})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["alerts"] == {"VCB": "Giá trên MA50", "HPG": "Giá trên MA50"}


def test_sectors_endpoint_shape():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/portfolio/sectors/f3")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["themes"]
    theme = body["themes"][0]
    assert set(theme) >= {"id", "name", "symbols", "kind"}
    assert theme["id"].startswith("f3:")
    assert theme["kind"] == "f3"


def test_f3_accordion_markup():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-atd-id="pb-ui:portfolio.f3-picker"' in html
    assert 'data-atd-id="pb-ui:iboard.f3.board"' in html
    assert "pb-ui:iboard.f3.sector." in html
    assert "Cảnh báo KT" in html
    assert "Sắp có" in html
    assert "pf-f3-expand-all" in html
    assert "pf-f3-theme-chip" not in html
    assert "/api/portfolio/alerts" in html
    assert "/api/iboard/equity-spark" in html
    assert "ensureF3Alerts" in html
