"""Regression: SSI live merge must keep board exchange (HNX/UPCOM tabs)."""

from backend.board_universe import FUTURES_BOARD_SYMBOLS
from backend.ssi_live import RealSsiWorker
from backend.tick_contract import build_tick


def test_build_topics_includes_futures_quote_depth():
    worker = RealSsiWorker()
    topics = worker._build_topics()
    for sym in FUTURES_BOARD_SYMBOLS:
        assert f"quote.{sym}" in topics
        assert f"quote.{sym}@tick" in topics
        assert f"trade.{sym}@tick" in topics
        assert f"room.{sym}" in topics
    assert "quote.VNINDEX" not in topics
    assert "indexsummary.VN30F1M" in topics


def test_topics_for_channel_x_quote_includes_futures():
    worker = RealSsiWorker()
    data_topics = worker._build_topics()
    xq = worker._topics_for_channel("X-Quote", data_topics)
    for sym in FUTURES_BOARD_SYMBOLS:
        assert sym in xq
    assert "VNINDEX" not in xq
    assert "FPT" in xq or "HPG" in xq
    assert worker._topics_for_channel("DATA", data_topics) is data_topics
    assert "quote.VN30F1M" in worker._topics_for_channel("DATA", data_topics)


def test_merge_tick_preserves_hnx_exchange():
    worker = RealSsiWorker()
    worker._board["SHS"] = build_tick(
        symbol="SHS",
        last=12_000,
        ref=12_000,
        exchange="HNX",
        volume=0,
        source="SSI_WS",
    )
    merged = worker._merge_tick(
        {
            "symbol": "SHS",
            "kind": "equity",
            "last": 12_050,
            "volume": 600_000,
        }
    )
    assert merged["exchange"] == "HNX"


def test_merge_tick_preserves_upcom_exchange():
    worker = RealSsiWorker()
    worker._board["ART"] = build_tick(
        symbol="ART",
        last=5_000,
        ref=5_000,
        exchange="UPCOM",
        volume=0,
        source="SSI_WS",
    )
    merged = worker._merge_tick(
        {
            "symbol": "ART",
            "kind": "equity",
            "last": 5_100,
            "foreignBuy": 1_000,
        }
    )
    assert merged["exchange"] == "UPCOM"
    assert merged["foreignBuy"] == 1_000


def test_merge_tick_hnx_even_when_prev_had_wrong_hose():
    worker = RealSsiWorker()
    worker._board["SHS"] = build_tick(
        symbol="SHS",
        last=12_000,
        ref=12_000,
        exchange="HOSE",
        volume=0,
        source="SSI_WS",
    )
    merged = worker._merge_tick({"symbol": "SHS", "kind": "equity", "last": 12_100})
    assert merged["exchange"] == "HNX"
