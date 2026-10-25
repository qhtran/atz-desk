"""Regression: SSI live merge must keep board exchange (HNX/UPCOM tabs)."""

from backend.ssi_live import RealSsiWorker
from backend.tick_contract import build_tick


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
