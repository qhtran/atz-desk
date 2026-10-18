"""Watchlist F3 wl_rows: cột Giá RT (T-237). Redis mock; không cần live Redis."""

from __future__ import annotations

from ui.watchlists_page import build_wl_symbol_rows


def test_wl_rows_headers_ma_gia_canh_bao():
    rows, redis_hits, priced = build_wl_symbol_rows(
        ["FPT", "VIC"],
        with_alerts=True,
        live_prices={"FPT": 99.5},
        alert_fn=lambda s: f"alert-{s}",
        ohlcv_fn=lambda s: 44.0 if s == "VIC" else None,
    )
    assert list(rows[0]) == ["Mã", "Giá", "Cảnh báo"]
    assert rows[0] == {"Mã": "FPT", "Giá": 99.5, "Cảnh báo": "alert-FPT"}
    assert rows[1] == {"Mã": "VIC", "Giá": 44.0, "Cảnh báo": "alert-VIC"}
    assert redis_hits == 1
    assert priced == 2


def test_wl_rows_redis_miss_and_ohlcv_miss_shows_dash():
    rows, redis_hits, priced = build_wl_symbol_rows(
        ["ZZZZ"],
        with_alerts=True,
        live_prices={},
        alert_fn=lambda _: "—",
        ohlcv_fn=lambda _: None,
    )
    assert rows[0]["Giá"] == "—"
    assert redis_hits == 0
    assert priced == 0


def test_wl_rows_without_alerts_has_no_gia_column():
    rows, redis_hits, priced = build_wl_symbol_rows(
        ["FPT"],
        with_alerts=False,
        live_prices={"FPT": 10.0},
    )
    assert list(rows[0]) == ["Mã"]
    assert redis_hits == 0
    assert priced == 0


def test_wl_rows_volumes_between_gia_and_alert():
    rows, _, _ = build_wl_symbol_rows(
        ["AAA"],
        volumes={"AAA": 1_234_567.0},
        with_alerts=True,
        live_prices={"AAA": 12.34},
        alert_fn=lambda _: "x",
        ohlcv_fn=lambda _: None,
    )
    assert list(rows[0]) == ["Mã", "Giá", "KL TB 10 phiên", "Cảnh báo"]
    assert rows[0]["Giá"] == 12.34


def test_wl_rows_batch_uses_injected_live_prices_once(monkeypatch):
    """Injected map = một batch; không gọi load_live_prices_thousands."""
    import ui.watchlists_page as wl

    def boom(_symbols):
        raise AssertionError("must not call Redis when live_prices injected")

    monkeypatch.setattr(wl, "load_live_prices_thousands", boom)
    rows, hits, _ = build_wl_symbol_rows(
        ["fpt", " vic "],
        with_alerts=True,
        live_prices={"FPT": 58.2},
        alert_fn=lambda _: "—",
        ohlcv_fn=lambda _: None,
    )
    assert hits == 1
    assert [r["Mã"] for r in rows] == ["FPT", "VIC"]
    assert rows[0]["Giá"] == 58.2
    assert rows[1]["Giá"] == "—"
