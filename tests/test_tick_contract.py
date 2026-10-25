"""Priceboard tick_contract: SSI envelope parse + build_tick."""

from __future__ import annotations

import pytest

from backend.tick_contract import build_tick, parse_ssi_envelope, ssi_envelope_has_symbol


def test_parse_index_prefers_v_not_c():
    """SSI indexsummary: v=level, c=change — never use c as last."""
    parsed = parse_ssi_envelope(
        {
            "channel": "DATA",
            "data": {
                "s": "VNINDEX",
                "v": "1699.81",
                "c": "7.84",
                "cr": "0.46",
                "tq": "85990007",
                "ce": "5",
                "fl": "2",
            },
        }
    )
    assert parsed is not None
    assert parsed["symbol"] == "VNINDEX"
    assert parsed["kind"] == "index"
    assert parsed["last"] == pytest.approx(1699.81)
    assert parsed["change"] == pytest.approx(7.84)
    assert parsed["change_pct"] == pytest.approx(0.46)
    assert parsed["volume"] == pytest.approx(85990007)
    assert parsed["ref"] == pytest.approx(1691.97)
    # ce/fl are advance/decline counts — not price limits
    assert parsed["ceil"] is None
    assert parsed["floor"] is None


def test_parse_hnxupcom_alias():
    parsed = parse_ssi_envelope(
        {"channel": "DATA", "data": {"s": "HNXUPCOMINDEX", "v": "125.86", "c": "0.64", "cr": "0.51"}}
    )
    assert parsed is not None
    assert parsed["symbol"] == "UPCOMINDEX"
    assert parsed["last"] == pytest.approx(125.86)


def test_parse_equity_trade_p_and_volume_v():
    """SSI equity trade: p=last, v=accum volume, o=open/ref."""
    parsed = parse_ssi_envelope(
        {
            "channel": "DATA",
            "data": {
                "s": "FPT",
                "p": "58000",
                "q": "200",
                "o": "58300",
                "h": "58300",
                "l": "57900",
                "v": "614100",
            },
        }
    )
    assert parsed is not None
    assert parsed["kind"] == "equity"
    assert parsed["last"] == 58000
    assert parsed["volume"] == 614100
    assert parsed["ref"] == 58300
    assert parsed["high"] == 58300
    assert parsed["low"] == 57900
    assert parsed["matchVol"] == 200


def test_parse_equity_book_bids_asks():
    parsed = parse_ssi_envelope(
        {
            "channel": "DATA",
            "data": {
                "s": "HPG",
                "bids": [["21050", "72800"], ["21000", "308400"], ["20950", "243200"], ["0", "0"]],
                "asks": [["21100", "199300"], ["21150", "69600"], ["21200", "190600"]],
            },
        }
    )
    assert parsed is not None
    assert parsed["last"] is None  # depth-only
    assert parsed["bid1"] == 21050
    assert parsed["bidVol1"] == 72800
    assert parsed["ask1"] == 21100
    assert parsed["askVol2"] == 69600


def test_parse_ignores_heartbeat():
    assert parse_ssi_envelope({"method": "PING", "channel": "HEARTBEAT"}) is None


def test_build_tick_ignores_zero_ceil_floor():
    tick = build_tick(symbol="FPT", last=58000, ref=58300, ceil=0, floor=0, kind="equity")
    assert tick["ceil"] > 0
    assert tick["floor"] > 0
    assert tick["ceil"] > tick["ref"] > tick["floor"]


def test_build_tick_index_from_parsed():
    parsed = parse_ssi_envelope(
        {"data": {"s": "VN30", "v": "1851.17", "c": "5.66", "cr": "0.31", "tq": "21042392"}}
    )
    assert parsed is not None
    tick = build_tick(
        symbol=parsed["symbol"],
        last=parsed["last"],
        ref=parsed["ref"],
        volume=parsed["volume"],
        kind=parsed["kind"],
        change=parsed["change"],
        change_pct=parsed["change_pct"],
        source="SSI_WS",
    )
    assert tick["last"] == pytest.approx(1851.17)
    assert tick["change_pct"] == pytest.approx(0.31)
    assert tick["volume"] == 21042392
    assert abs(tick["change_pct"]) < 5


def test_parse_index_trade_volume_v_not_used_as_last():
    """trade.index style: large v is volume — must not become index last."""
    parsed = parse_ssi_envelope(
        {"channel": "DATA", "data": {"s": "VNINDEX", "p": "1700.5", "q": "10", "v": "99433205"}}
    )
    assert parsed is not None
    assert parsed["last"] == pytest.approx(1700.5)
    assert parsed["volume"] == pytest.approx(99433205)


def test_parse_index_rejects_huge_v_without_summary():
    assert parse_ssi_envelope({"data": {"s": "VNINDEX", "v": "99433205"}}) is None
    assert ssi_envelope_has_symbol({"data": {"s": "VNINDEX", "v": "99433205"}})


def test_parse_x_quote_depth_only_no_last():
    """P1 skeleton: X-Quote partial — merge path expects depth without last."""
    parsed = parse_ssi_envelope(
        {
            "channel": "X-Quote",
            "data": {
                "s": "FPT",
                "bidPrice1": "95000",
                "bidVolume1": "1200",
                "offerPrice1": "95100",
                "offerVolume1": "800",
            },
        }
    )
    assert parsed is not None
    assert parsed["last"] is None
    assert parsed["bid1"] == 95000
    assert parsed["ask1"] == 95100
    assert parsed["bidVol1"] == 1200
    assert parsed["channel"] == "X-QUOTE"


def test_parse_mi_foreign_only_no_last():
    parsed = parse_ssi_envelope(
        {
            "channel": "MI",
            "data": {"StockSymbol": "HPG", "fBuyVol": "15000", "fSellVol": "22000"},
        }
    )
    assert parsed is not None
    assert parsed["last"] is None
    assert parsed["foreignBuy"] == 15000
    assert parsed["foreignSell"] == 22000


def test_ssi_envelope_has_symbol_false_on_heartbeat():
    assert not ssi_envelope_has_symbol({"method": "PING", "channel": "HEARTBEAT"})
