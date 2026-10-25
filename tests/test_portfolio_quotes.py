"""Phase B portfolio quotes — parity wl_rows price merge (server-side)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.portfolio_quotes import (
    normalize_symbols,
    ohlcv_avg_volume_10,
    ohlcv_last_close_vnd,
    resolve_portfolio_quotes,
)


def test_normalize_symbols_dedup():
    assert normalize_symbols("fpt, VIC ,fpt") == ["FPT", "VIC"]


def test_wl_rows_price_merge_priceboard_then_ohlcv(tmp_path: Path):
    """Tương đương test_wl_rows_headers_ma_gia_canh_bao (giá VND cho SPA)."""
    vic_csv = tmp_path / "VIC.csv"
    vic_csv.write_text("close,volume\n44.0,1000\n44.0,2000\n", encoding="utf-8")
    quotes, pb_hits, priced = resolve_portfolio_quotes(
        ["FPT", "VIC"],
        bars_dir=tmp_path,
        priceboard={"FPT": 99500.0},
        legacy={},
    )
    assert pb_hits == 1
    assert priced == 2
    assert quotes["FPT"]["price"] == 99500.0
    assert quotes["FPT"]["price_source"] == "priceboard"
    assert quotes["VIC"]["price"] == 44000
    assert quotes["VIC"]["price_source"] == "ohlcv"


def test_wl_rows_miss_shows_null_price(tmp_path: Path):
    quotes, pb_hits, priced = resolve_portfolio_quotes(
        ["ZZZZ"],
        bars_dir=tmp_path,
        priceboard={},
        legacy={},
    )
    assert pb_hits == 0
    assert priced == 0
    assert quotes["ZZZZ"]["price"] is None


def test_wl_rows_avg_volume_10(tmp_path: Path):
    lines = ["close,volume"]
    for i in range(10):
        lines.append(f"10.0,{500_000 + i}")
    lines.append("10.0,900000")
    (tmp_path / "AAA.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    avg = ohlcv_avg_volume_10(tmp_path, "AAA")
    assert avg == pytest.approx(500_004.5)
    quotes, _, _ = resolve_portfolio_quotes(
        ["AAA"],
        bars_dir=tmp_path,
        priceboard={"AAA": 12340.0},
        legacy={},
    )
    assert quotes["AAA"]["avg_volume_10"] == pytest.approx(500_004.5)


def test_legacy_quote_fallback_vnd(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "backend.portfolio_quotes.load_legacy_quote_prices",
        lambda symbols, **_: {"ZZZ": 58200} if "ZZZ" in symbols else {},
    )
    quotes, _, priced = resolve_portfolio_quotes(
        ["ZZZ"],
        bars_dir=tmp_path,
        priceboard={},
        legacy=None,
    )
    assert priced == 1
    assert quotes["ZZZ"]["price"] == 58200
    assert quotes["ZZZ"]["price_source"] == "legacy_quote"


def test_ohlcv_last_close_vnd():
    assert ohlcv_last_close_vnd(Path("/nonexistent"), "X") is None
