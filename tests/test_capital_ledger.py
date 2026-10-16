"""Sổ vốn sidebar + cảnh báo vị thế (F1 mục 2)."""

from __future__ import annotations

from datasource.capital_ledger import CapitalLedger, load_ledger, nav_breakdown, save_ledger
from ui.sidebar_portfolio import position_alert


def test_default_and_roundtrip(tmp_path):
    path = tmp_path / "capital_ledger.csv"
    loaded = load_ledger(path)
    assert loaded.initial > 0 and loaded.additional == 0 and loaded.withdrawn == 0
    save_ledger(CapitalLedger(initial=50_000_000, additional=10_000_000, withdrawn=5_000_000), path)
    again = load_ledger(path)
    assert again.total == 55_000_000
    assert again.initial == 50_000_000


def test_nav_breakdown_cash_and_pnl():
    ledger = CapitalLedger(initial=100_000_000, additional=0, withdrawn=0)
    snap = nav_breakdown(ledger, securities_cost=40_000_000, securities_mkt=45_000_000)
    assert snap["cash"] == 60_000_000
    assert snap["nav"] == 105_000_000
    assert snap["pnl"] == 5_000_000


def test_position_alert_bands_and_zones():
    assert position_alert(None, None) == "Chưa có giá"
    assert "Gần hỗ trợ" in position_alert(10.0, 10.1, support=10.0)
    assert position_alert(10.0, 10.6) == "+5%"
    assert position_alert(10.0, 9.1) == "−8%"
    assert position_alert(10.0, 10.1) == "—"
