"""SSI REST bootstrap → priceboard ticks."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from backend.ssi_rest_bootstrap import (
    SsiRestClient,
    bootstrap_ticks,
    equity_tick_from_summary,
    index_tick_from_summary,
    last_trading_date_vn,
    needs_rest_bootstrap,
    _vnd_price,
)


def test_needs_rest_bootstrap_empty_or_zero():
    assert needs_rest_bootstrap(None) is True
    assert needs_rest_bootstrap({"last": 0, "ref": 0}) is True
    assert needs_rest_bootstrap({"last": 100, "ref": 99}) is False


def test_last_trading_date_skips_weekend():
    sat = datetime(2026, 10, 24, 12, 0, tzinfo=timezone(timedelta(hours=7)))
    assert last_trading_date_vn(sat) == "2026/10/23"


def test_vnd_price_thousands_for_equity():
    assert _vnd_price(45.5, symbol="SSI") == 45500
    assert _vnd_price(1847.0, symbol="VN30F1M") == 1847.0


def test_index_tick_from_summary():
    tick = index_tick_from_summary(
        {"indexValue": "1705.91", "indexChange": "7.56", "indexChangePercentage": "0.44"},
        "VNINDEX",
    )
    assert tick["symbol"] == "VNINDEX"
    assert tick["last"] == 1705.91
    assert tick["ref"] == 1698.35
    assert tick["source"] == "SSI_REST"


def test_equity_tick_from_summary():
    tick = equity_tick_from_summary(
        {
            "close": "118.5",
            "priceChange": "1.2",
            "priceChangePercentage": "1.02",
            "average": "117.3",
            "totalMatch": "2500000",
        },
        "FPT",
    )
    assert tick["symbol"] == "FPT"
    assert tick["last"] == 118500
    assert tick["volume"] == 2500000


class FakeSession:
    def __init__(self, responder):
        self._responder = responder
        self.calls: list[str] = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        payload = self._responder(url)

        class R:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        return R()


def test_bootstrap_ticks_index_and_equity():
    td = "2026/10/23"

    def responder(url: str):
        if "indexSummary" in url and "VNINDEX" in url:
            return [{"indexValue": "1700", "indexChange": "0", "tradingDate": td}]
        if "securitiesSummary" in url and "FPT" in url:
            return {"data": [{"close": "100", "priceChange": "0", "average": "100", "tradingDate": td}]}
        raise AssertionError(url)

    client = SsiRestClient("tok", session=FakeSession(responder))
    ticks = bootstrap_ticks(
        client,
        index_symbols=["VNINDEX"],
        equity_symbols=["FPT"],
        trading_date=td,
        sleep_between_equity=0,
    )
    syms = {t["symbol"] for t in ticks}
    assert syms == {"VNINDEX", "FPT"}
