"""Regression: SSI live merge must keep board exchange (HNX/UPCOM tabs)."""

from unittest.mock import AsyncMock

import pytest

from backend.board_universe import FUTURES_BOARD_SYMBOLS
from backend.futures_contracts import load_futures_contract_map
from backend.ssi_live import RealSsiWorker
from backend.tick_contract import build_tick, parse_ssi_envelope


def test_build_topics_includes_futures_contract_quote_depth():
    worker = RealSsiWorker()
    topics = worker._build_topics()
    fmap = load_futures_contract_map()
    for board in FUTURES_BOARD_SYMBOLS:
        code = fmap[board]
        assert f"quote.{code}" in topics
        assert f"quote.{code}@tick" in topics
        assert f"trade.{code}@tick" in topics
        assert f"room.{code}" in topics
        assert f"quote.{board}" not in topics
    assert "quote.VNINDEX" not in topics
    assert "indexsummary.VN30F1M" in topics


def test_topics_for_channel_x_quote_includes_futures_contracts():
    worker = RealSsiWorker()
    data_topics = worker._build_topics()
    xq = worker._topics_for_channel("X-Quote", data_topics)
    fmap = load_futures_contract_map()
    for board in FUTURES_BOARD_SYMBOLS:
        assert fmap[board] in xq
        assert board not in xq
    assert "VNINDEX" not in xq
    assert "FPT" in xq or "HPG" in xq
    assert "quote.41I1GB000" in worker._topics_for_channel("DATA", data_topics)


def test_remap_futures_contract_to_board_symbol():
    worker = RealSsiWorker()
    parsed = parse_ssi_envelope(
        {
            "channel": "X-Quote",
            "data": {
                "s": "41I1GB000",
                "bidPrice1": "1891.0",
                "bidVolume1": "12",
                "offerPrice1": "1892.0",
                "offerVolume1": "8",
            },
        }
    )
    assert parsed is not None
    remapped = worker._remap_futures_symbol(parsed)
    assert remapped["symbol"] == "VN30F1M"
    assert remapped["contract"] == "41I1GB000"
    assert remapped["bid1"] == 1891.0
    assert remapped["ask1"] == 1892.0
    tick = worker._merge_tick(remapped)
    assert tick["symbol"] == "VN30F1M"
    assert tick["bid1"] == 1891.0
    assert tick["ask1"] == 1892.0


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


@pytest.mark.asyncio
async def test_purge_removed_core_hdel_and_publish_remove():
    worker = RealSsiWorker()
    worker._board["ZZZ"] = build_tick(symbol="ZZZ", last=1, ref=1, exchange="HOSE")
    worker._board["YYY"] = build_tick(symbol="YYY", last=1, ref=1, exchange="HNX")
    worker._board["KEEP"] = build_tick(symbol="KEEP", last=1, ref=1, exchange="HOSE")
    redis = AsyncMock()
    redis.hdel = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)
    n = await worker._purge_removed_core_from_board(redis, ["ZZZ", "", "yyy"])
    assert n == 2
    assert "ZZZ" not in worker._board
    assert "YYY" not in worker._board
    assert "KEEP" in worker._board
    assert redis.hdel.await_count == 2
    assert redis.publish.await_count == 2
    published = redis.publish.await_args_list[0].args[1]
    assert '"type":"remove"' in published.replace(" ", "")
    assert "ZZZ" in published


@pytest.mark.asyncio
async def test_reconcile_board_hash_drops_off_universe():
    worker = RealSsiWorker()
    worker.symbols = ["AAA", "BBB"]
    worker._ondemand_active = {"OD1"}
    redis = AsyncMock()
    redis.hkeys = AsyncMock(return_value=["AAA", "OLD1", "OD1", "VNINDEX", "old2"])
    redis.hdel = AsyncMock(return_value=1)
    redis.publish = AsyncMock(return_value=1)
    n = await worker._reconcile_board_hash_to_universe(redis)
    assert n == 2
    purged = {c.args[1] for c in redis.hdel.await_args_list}
    assert purged == {"OLD1", "OLD2"}
