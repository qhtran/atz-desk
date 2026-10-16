"""Top KL phiên so với TB 10 (F1 mục 5)."""

from __future__ import annotations

import pandas as pd

from analysis.volume_leaders import rank_volume_leaders, volume_stats


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
    )
    assert board["Mã"].tolist() == ["AAA", "BBB"]
    assert board.iloc[0]["KL / TB10"] > board.iloc[1]["KL / TB10"]
