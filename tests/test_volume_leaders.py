"""Top KL phiên so với TB 10 (F1 mục 5) + Redis price overlay."""

from __future__ import annotations

import json

import pandas as pd

from analysis.volume_leaders import (
    apply_live_price_overlay,
    bar_session_date,
    rank_volume_leaders,
    volume_stats,
)
from datasource.live_quotes import load_live_session_quotes


def _bars(last_vol: float, avg: float, n: int = 15, last_close: float = 10.0) -> pd.DataFrame:
    """n phiên; TB 10 phiên trước = avg; phiên cuối = last_vol."""
    volumes = [avg] * (n - 1) + [last_vol]
    closes = [last_close - 0.1] * (n - 1) + [last_close]
    return pd.DataFrame({"close": closes, "volume": volumes})


def test_volume_stats_ratio():
    stats = volume_stats(_bars(1_500_000, 500_000))
    assert stats is not None
    assert stats["avg_volume"] == 500_000
    assert stats["last_volume"] == 1_500_000
    assert stats["ratio"] == 3.0


def test_rank_filters_min_avg_and_sorts(tmp_path):
    hot = _bars(2_000_000, 600_000)
    mild = _bars(700_000, 550_000)
    quiet = _bars(2_000_000, 100_000)  # dưới sàn 500k
    for name, frame in (("AAA", hot), ("BBB", mild), ("CCC", quiet)):
        frame.to_csv(tmp_path / f"{name}.csv", index=False)
    board = rank_volume_leaders(
        symbols=["AAA", "BBB", "CCC"],
        bars_dir=tmp_path,
        min_avg=500_000,
        top_n=20,
        use_live=False,
    )
    assert board["Mã"].tolist() == ["AAA", "BBB"]
    assert board.iloc[0]["KL / TB10"] > board.iloc[1]["KL / TB10"]
    assert isinstance(board.iloc[0]["Xu hướng"], list) and len(board.iloc[0]["Xu hướng"]) >= 2
    assert board.attrs.get("price_source") == "ohlcv"


def test_bar_session_date():
    frame = pd.DataFrame(
        {"time": ["2026-10-15", "2026-10-16"], "close": [1.0, 2.0], "volume": [1, 2]}
    )
    assert bar_session_date(frame) == "2026-10-16"
    assert bar_session_date(pd.DataFrame({"close": [1.0]})) is None


def test_apply_live_overlay_updates_price_and_pct():
    board = pd.DataFrame(
        [
            {
                "Mã": "VHM",
                "Giá": 58.9,
                "KL phiên": 1.0,
                "KL TB 10 phiên": 1.0,
                "KL / TB10": 1.0,
                "Biến động giá (%)": -1.0,
                "Xu hướng": [1, 2],
            }
        ]
    )
    out, hits = apply_live_price_overlay(
        board,
        {"VHM": {"price_k": 61.0, "change_pct": 3.57}},
    )
    assert hits == 1
    assert out.iloc[0]["Giá"] == 61.0
    assert out.iloc[0]["Biến động giá (%)"] == 3.57


def test_rank_live_overlay_wins_over_ohlcv(tmp_path):
    # OHLCV «TC» 58.9 / Δ âm — Redis phiên 61 / +3.57
    frame = _bars(2_000_000, 600_000, last_close=58.9)
    frame["time"] = [f"2026-10-{i:02d}" for i in range(1, 16)]
    frame.to_csv(tmp_path / "VHM.csv", index=False)
    quotes = {"VHM": {"price_k": 61.0, "change_pct": 3.57}}
    board = rank_volume_leaders(
        symbols=["VHM"],
        bars_dir=tmp_path,
        min_avg=500_000,
        live_quotes=quotes,
        use_live=True,
    )
    assert board.iloc[0]["Giá"] == 61.0
    assert board.iloc[0]["Biến động giá (%)"] == 3.57
    assert board.attrs["price_source"] == "redis"
    assert board.attrs["redis_overlay_count"] == 1
    assert board.attrs["ohlcv_session_date"] == "2026-10-15"


def test_load_live_session_quotes_from_ref():
    class _Fake:
        def mget(self, keys):
            return [
                json.dumps({"price": 61000, "ref_price": 58900, "change_pct": 3.57}),
                json.dumps({"price": 25000}),  # thiếu % + ref → bỏ
            ]

    got = load_live_session_quotes(
        ["VHM", "STB"],
        client=_Fake(),
        quote_key="quote:{symbol}",
    )
    assert got["VHM"]["price_k"] == 61.0
    assert got["VHM"]["change_pct"] == 3.57
    assert "STB" not in got
