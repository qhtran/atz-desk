"""Universe board_stocks + resolve_symbols (T-13b / full-board 1-shot)."""

from __future__ import annotations

import pandas as pd

from ingestion.universe import board_stock_symbols, resolve_symbols


def test_resolve_static_ignores_listing():
    assert resolve_symbols("static", [" fpt ", "VCB", ""]) == ["FPT", "VCB"]


def test_resolve_board_stocks_uses_listing(monkeypatch):
    import ingestion.universe as uni

    monkeypatch.setattr(
        uni,
        "board_stock_symbols",
        lambda: ["AAA", "VNM", "FPT"],
    )
    assert resolve_symbols("board_stocks", ["SSI"]) == ["AAA", "VNM", "FPT"]


def test_resolve_board_stocks_falls_back_on_error(monkeypatch):
    import ingestion.universe as uni

    def boom():
        raise RuntimeError("listing down")

    monkeypatch.setattr(uni, "board_stock_symbols", boom)
    assert resolve_symbols("board_stocks", ["SSI", "FPT"]) == ["SSI", "FPT"]


def test_board_stock_symbols_filters_type(monkeypatch):
    class FakeListing:
        def symbols_by_exchange(self):
            return pd.DataFrame(
                {
                    "symbol": ["fpt", "ABC", "X1", "ZZ", "VNM"],
                    "type": ["stock", "cw", "stock", "stock", "STOCK"],
                    "exchange": ["HOSE", "HOSE", "HNX", "UPCOM", "HOSE"],
                }
            )

    monkeypatch.setattr("vnstock.Listing", FakeListing)
    got = board_stock_symbols()
    # cw + symbol < 3 chars bị loại
    assert got == ["FPT", "VNM"]
