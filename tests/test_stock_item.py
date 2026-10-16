"""StockItem + sparkline series (P0 FireAnt-style)."""

from __future__ import annotations

import pandas as pd

from datasource.spark_series import closes_sparkline, load_sparkline
from ui.stock_item import StockItem, realtime_board_frame
from ui.sparkline import sparkline_svg


def test_stock_item_from_quote_and_sign():
    item = StockItem.from_quote(
        {"symbol": "fpt", "price": 100000, "change": 1000, "change_pct": 1.0, "volume": 1e6, "ref_price": 99000},
        sparkline=[90.0, 91.0],
    )
    assert item.ticker == "FPT"
    assert item.is_positive
    assert item.with_live_on_spark().sparkline[-1] == 100.0  # VND → nghìn


def test_closes_and_load_sparkline(tmp_path):
    frame = pd.DataFrame({"close": [10.0 + i * 0.1 for i in range(25)], "volume": [1e6] * 25})
    assert len(closes_sparkline(frame, n=5)) == 5
    frame.to_csv(tmp_path / "AAA.csv", index=False)
    spark = load_sparkline("AAA", bars_dir=tmp_path, n=5, live_price_vnd=15_000)
    assert spark[-1] == 15.0
    assert len(spark) == 6


def test_realtime_board_frame_inserts_trend(tmp_path):
    pd.DataFrame({"close": [20.0, 21.0, 22.0], "volume": [1, 1, 1]}).to_csv(tmp_path / "BBB.csv", index=False)
    rows = [{"Mã": "BBB", "Giá": 23000.0, "%": 1.0, "Trạng thái": "live", "_stale": False}]
    board = realtime_board_frame(rows, bars_dir=tmp_path, spark_bars=3)
    assert "Xu hướng" in board.columns
    assert board.iloc[0]["Xu hướng"][-1] == 23.0


def test_sparkline_svg_nonempty():
    svg = sparkline_svg([1.0, 2.0, 1.5], ref=1.2, uid="t1")
    assert "polyline" in svg and "clipPath" in svg
