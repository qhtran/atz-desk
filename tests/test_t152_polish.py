"""T-152 P1 polish: exclude index Top KL; quote status/format; ngoài rổ caption."""

from __future__ import annotations

from datetime import datetime

from analysis.volume_leaders import is_index_symbol, rank_volume_leaders
from ui_realtime import data
from ui_realtime.log import TZ


def test_is_index_symbol_covers_truncation():
    assert is_index_symbol("VNINDEX")
    assert is_index_symbol("VNINDE")
    assert is_index_symbol("vn30f1m")
    assert is_index_symbol("HNXINDEX")
    assert not is_index_symbol("POW")
    assert not is_index_symbol("VHM")


def test_rank_excludes_index_csv(tmp_path):
    import pandas as pd

    n, avg, last_vol = 15, 600_000.0, 2_000_000.0
    frame = pd.DataFrame(
        {
            "close": [10.0] * (n - 1) + [10.1],
            "volume": [avg] * (n - 1) + [last_vol],
        }
    )
    frame.to_csv(tmp_path / "AAA.csv", index=False)
    frame.to_csv(tmp_path / "VNINDEX.csv", index=False)
    frame.to_csv(tmp_path / "VNINDE.csv", index=False)
    board = rank_volume_leaders(
        symbols=["AAA", "VNINDEX", "VNINDE"],
        bars_dir=tmp_path,
        min_avg=500_000,
        use_live=False,
    )
    assert board["Mã"].tolist() == ["AAA"]


def test_quote_rows_closed_outside_session_and_ceiling_int():
    now = datetime(2026, 10, 17, 15, 40, tzinfo=TZ)  # thứ 7 ngoài phiên
    quotes = [
        {
            "symbol": "TPB",
            "timestamp": now.isoformat(timespec="seconds"),
            "price": 12000,
            "change": 0,
            "change_pct": 0.0,
            "open": 12000,
            "high": 12000,
            "low": 12000,
            "ref_price": 12000,
            "ceiling_price": 12550.000000,
            "floor_price": 11450.5,
            "source": "kbs",
            "stale": False,
            "exchange": "HOSE",
        }
    ]
    rows = data.quote_rows(quotes, stale_seconds=120, now=now, trading=False)
    assert rows[0]["Trạng thái"] == "closed"
    assert rows[0]["Trần"] == 12550
    assert rows[0]["Sàn giá"] == 11450


def test_quote_status_label_matrix():
    assert data.quote_status_label(stale=True, trading=True) == "⚠️ cũ"
    assert data.quote_status_label(stale=False, trading=False) == "closed"
    assert data.quote_status_label(stale=False, trading=True) == "live"
