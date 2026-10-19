"""SSI stream Phase 1: parse + writer + index-feed defer to WS health."""
from __future__ import annotations

import json

import pytest

from ingestion.index.common import IdxQuote, load as load_index
from ingestion.index.feed import IndexFeed
from ingestion.ssi_stream.config import load as load_stream
from ingestion.ssi_stream.parse import normalize_symbol, parse_market_message
from ingestion.ssi_stream.writer import RedisWriter


@pytest.fixture
def settings():
    return load_index()


def test_normalize_and_parse_indexsummary():
    aliases = {"HNXIndex": "HNXINDEX"}
    assert normalize_symbol("HNXIndex", aliases) == "HNXINDEX"
    q = parse_market_message(
        {"type": "indexsummary", "data": {
            "symbol": "VNINDEX", "indexValue": "1689.84", "indexChange": "-16.07", "tradingDate": "2026/10/19",
        }},
        aliases,
    )
    assert q["symbol"] == "VNINDEX" and q["value"] == 1689.84 and q["ref"] == pytest.approx(1705.91)


def test_parse_trade_short_fields():
    q = parse_market_message({"s": "VN30", "p": "1839.18", "t": "2026/10/19 14:00:00"}, {})
    assert q["symbol"] == "VN30" and q["value"] == 1839.18


def test_parse_ignores_ping():
    assert parse_market_message({"method": "PING", "channel": "HEARTBEAT"}, {}) is None


class MemRedis:
    def __init__(self):
        self.kv = {}

    def pipeline(self):
        return self

    def set(self, k, v, ex=None):
        self.kv[k] = v
        return self

    def get(self, k):
        return self.kv.get(k)

    def execute(self):
        return True


def test_writer_sets_quote_source_ssi_ws():
    s = load_stream()
    r = MemRedis()
    w = RedisWriter(s, r, clock=lambda: 1_700_000_000)
    w.upsert_quote({"symbol": "VNINDEX", "value": 1700.0, "ref": 1690.0, "data_time": "t"})
    raw = json.loads(r.kv["idx:quote:VNINDEX"])
    assert raw["source"] == "SSI_WS" and raw["value"] == 1700.0


class FakeProv:
    name = "VIETCAP"

    def __init__(self):
        self.enabled = True
        self.calls = []

    def cost(self, symbols):
        return 1

    def quotes(self, symbols):
        self.calls.append(list(symbols))
        return {s: IdxQuote(s, 1.0, 1.0, "VIETCAP") for s in symbols if s.startswith("VN30F")}

    def bars(self, symbols, since):
        return {}


def test_index_feed_defers_spot_when_stream_healthy(settings):
    settings.stream_backup_enabled = True
    settings.stream_health_key = "ssi_stream:health"
    settings.stream_max_age = 30
    settings.stream_spot_symbols = ("VNINDEX", "HNXINDEX", "UPCOMINDEX", "VN30")
    r = MemRedis()
    now = 1_700_000_100
    r.kv["ssi_stream:health"] = json.dumps({"healthy": True, "epoch": now})
    r.kv["idx:quote:VNINDEX"] = json.dumps({
        "symbol": "VNINDEX", "value": 1689.84, "ref": 1705.91, "change": -16.07, "pct": -0.94,
        "ts": now, "source": "SSI_WS", "data_time": None, "contract": None,
    })
    fake = FakeProv()
    feed = IndexFeed(settings, r, providers=[fake], clock=lambda: now)
    # replace sparks symbols already from settings
    q = feed.cycle()
    assert q["VNINDEX"].source == "SSI_WS"
    assert fake.calls and all("VNINDEX" not in c for c in fake.calls)
    assert "VN30F1M" in q
