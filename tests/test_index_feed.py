"""Index sparkline: T1 parse provider + failover, T2 spark/ref split/rollover, T3 UI 6 thẻ + stale/fallback, T4 provider down."""
from __future__ import annotations

import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ingestion.circuit_breaker import OPEN
from ingestion.index import common, providers as P
from ingestion.index.common import IdxQuote, ProviderDown
from ingestion.index.feed import IndexFeed
from ingestion.index.series import Spark, in_session, seconds_to_next_session, split_by_ref
from ui_realtime import index_cards as IC

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
SYMS = ["VNINDEX", "HNXINDEX", "UPCOMINDEX", "VN30", "VN30F1M", "VN30F2M"]

VCI_MI = [  # trích response thật marketIndex/getList 2026-10-16
    {"symbol": "VNINDEX", "price": 1705.91, "refPrice": 1698.35, "time": "2026-10-16T07:45:59.999Z"},
    {"symbol": "HNXIndex", "price": 259.13, "refPrice": 259.29, "time": "2026-10-16T07:45:59.999Z"},
    {"symbol": "HNXUpcomIndex", "price": 124.87, "refPrice": 124.15, "time": "2026-10-16T08:00:59.999Z"},
    {"symbol": "VN30", "price": 1855.41, "refPrice": 1843.71, "time": "2026-10-16T07:45:59.999Z"}]
VCI_FU = [
    {"listingInfo": {"symbol": "41I1GB000", "refPrice": 1847, "maturityDate": "20/11/2026", "mappingSymbol": "VN30F1M"},
     "matchPrice": {"matchPrice": 1855.1, "referencePrice": 1847, "time": "2026-10-16T07:45:00.153Z"}},
    {"listingInfo": {"symbol": "41I1GC000", "refPrice": 1850.2, "maturityDate": "18/12/2026", "mappingSymbol": "VN30F2M"},
     "matchPrice": {"matchPrice": 1858.0, "referencePrice": 1850.2, "time": "2026-10-16T07:45:00.153Z"}}]
VCI_GAP = [{"symbol": "VNINDEX", "t": ["1792135560", "1792135620"], "c": [1703.92, 1703.36]},
           {"symbol": "41I1GB000", "t": ["1792135560"], "c": [1855.0]}]
ENT_BARS = {"t": [1792135560, 1792135620], "o": [1, 1], "h": [1, 1], "l": [1, 1], "c": [1703.92, 1705.91], "v": [1, 1]}
ENT_1D = {"t": [1791936000, 1792022400, 1792108800], "c": [1690.0, 1698.35, 1705.91]}


@pytest.fixture
def settings():
    return common.load()


class FakeHTTP:
    def __init__(self, routes):
        self.routes, self.headers, self.calls = routes, {}, []

    def request(self, method, url, timeout=None, params=None, json=None):
        self.calls.append((method, url, params, json))
        key = url.rsplit("/", 1)[-1]
        if key in ("index", "derivative"):
            key += "_1D" if params["resolution"] == "1D" else ""
        body = self.routes[key]
        if isinstance(body, Exception):
            raise body

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return body
        return R()


# ------------------------------------------------------------------ T1
def test_t1_parse_vietcap_all_six():
    q = P.parse_vci_market_index(VCI_MI)
    fq, contracts = P.parse_vci_futures(VCI_FU)
    q.update(fq)
    assert sorted(q) == sorted(SYMS)
    assert q["VNINDEX"].value == 1705.91 and q["VNINDEX"].ref == 1698.35 and q["VNINDEX"].change == 7.56
    assert q["UPCOMINDEX"].value == 124.87   # live từ marketIndex, không lấy bar 1m cuối
    assert contracts["VN30F1M"] == {"code": "41I1GB000", "maturity": "2026-11-20"}
    assert q["VN30F1M"].contract == "41I1GB000" and q["VN30F1M"].pct == round(8.1 / 1847 * 100, 2)
    bars = P.parse_vci_bars(VCI_GAP, {"VNINDEX": "VNINDEX", "41I1GB000": "VN30F1M"})
    assert bars["VNINDEX"] == [(1792135560, 1703.92), (1792135620, 1703.36)]


def test_t1_parse_entrade_all_six(settings):
    http = FakeHTTP({"index": ENT_BARS, "derivative": ENT_BARS, "index_1D": ENT_1D, "derivative_1D": ENT_1D})
    ent = P.Entrade(settings, session=http, clock=lambda: 1792140000)
    q = ent.quotes(SYMS)
    assert sorted(q) == sorted(SYMS)
    assert q["VNINDEX"].value == 1705.91 and q["VNINDEX"].ref == 1698.35
    codes = {c[2]["symbol"] for c in http.calls}
    assert {"VNINDEX", "HNX", "UPCOM", "VN30", "VN30F1M", "VN30F2M"} <= codes
    assert P.parse_ent_bars(ENT_BARS)[-1] == (1792135620, 1705.91)


def test_t1_ssi_disabled_without_env(settings):
    ssi = P.SSI(settings, session=FakeHTTP({}))
    assert ssi.enabled is (bool(settings.env["SSI_CONSUMER_ID"]) and bool(settings.env["SSI_CONSUMER_SECRET"]))
    settings.env.update(SSI_CONSUMER_ID="", SSI_CONSUMER_SECRET="")
    with pytest.raises(ProviderDown):
        ssi.quotes(SYMS)


class Fake:
    def __init__(self, name, data=None, fail=False, enabled=True):
        self.name, self.data, self.fail, self._en, self.calls = name, data or {}, fail, enabled, 0
        self.contracts = {}

    @property
    def enabled(self):
        return self._en

    def cost(self, s):
        return 1

    def quotes(self, symbols):
        self.calls += 1
        if self.fail:
            raise ProviderDown(self.name + " down")
        return {s: IdxQuote(s, *self.data[s], self.name) for s in symbols if s in self.data}

    def bars(self, symbols, since):
        if self.fail:
            raise ProviderDown("down")
        return {s: [(1792135560, self.data[s][0])] for s in symbols if s in self.data}


class FakeRedis:
    def __init__(self, fail=False):
        self.kv, self.fail = {}, fail

    def pipeline(self):
        return self

    def set(self, k, v, ex=None):
        if self.fail:
            raise ConnectionError("redis down")
        self.kv[k] = v

    def execute(self):
        if self.fail:
            raise ConnectionError("redis down")

    def mget(self, keys):
        return [self.kv.get(k) for k in keys]


def test_t1_failover_order_per_symbol(settings):
    ssi = Fake("SSI", enabled=False)
    ent = Fake("ENTRADE", {"VNINDEX": (1.0, 1.0)})
    vci = Fake("VIETCAP", {s: (2.0, 1.0) for s in SYMS})
    feed = IndexFeed(settings, FakeRedis(), providers=[ssi, ent, vci])
    q = feed.cycle()
    assert ssi.calls == 0
    assert q["VNINDEX"].source == "ENTRADE" and q["VN30F2M"].source == "VIETCAP"
    assert [e["p"].name for e in feed.providers] == ["SSI", "ENTRADE", "VIETCAP"]


# ------------------------------------------------------------------ T2
def _ep(h, m, day=16):
    return datetime(2026, 10, day, h, m, 5, tzinfo=TZ).timestamp()


def test_t2_spark_minute_aggregation_and_day_reset():
    sp = Spark("VNINDEX", "Asia/Ho_Chi_Minh", max_points=3)
    for m, v in [(0, 1.0), (0, 1.5), (1, 2.0), (2, 3.0), (3, 4.0)]:
        sp.add(_ep(10, m), v)
    assert [p[1] for p in sp.points] == [2.0, 3.0, 4.0]   # cùng phút ghi đè, giới hạn max điểm
    sp.add(_ep(9, 0, day=19), 9.0)
    assert len(sp.points) == 1 and sp.points[0][1] == 9.0   # phiên mới -> reset


def test_t2_backfill_keeps_latest_session_only():
    sp = Spark("VN30", "Asia/Ho_Chi_Minh")
    sp.load([(int(_ep(14, 0, 15)), 1.0), (int(_ep(9, 15)), 2.0), (int(_ep(9, 16)), 3.0)])
    assert [p[1] for p in sp.points] == [2.0, 3.0]


def test_t2_ref_split_coloring():
    assert split_by_ref([1, 3, 4, 2, 0.5], 2.5) == [("down", [0]), ("up", [1, 2]), ("down", [3, 4])]
    svg = IC.sparkline_svg([1, 3, 4, 2], 2.5, "T")
    assert IC.YELLOW in svg and IC.GREEN in svg and IC.RED in svg and "<circle" in svg
    assert 'clip-path="url(#up-T)"' in svg and 'clip-path="url(#dn-T)"' in svg


def test_t2_futures_rollover_resets_series(settings):
    sp = Spark("VN30F1M", "Asia/Ho_Chi_Minh")
    sp.load([(int(_ep(9, 0)), 1.0)], contract="41I1GA000")
    assert sp.roll_if_needed("41I1GA000") is False and sp.points
    assert sp.roll_if_needed("41I1GB000") is True and sp.points == [] and sp.contract == "41I1GB000"


def test_t2_sessions_and_ttl():
    s = [["08:45", "11:30"], ["13:00", "15:00"]]
    assert in_session(_ep(10, 0), "Asia/Ho_Chi_Minh", s) and not in_session(_ep(12, 0), "Asia/Ho_Chi_Minh", s)
    assert not in_session(_ep(10, 0, 17), "Asia/Ho_Chi_Minh", s)   # thứ 7
    ttl = seconds_to_next_session(_ep(15, 30), "Asia/Ho_Chi_Minh", s)   # thứ 6 -> thứ 2 08:45 + 1h
    assert 2.7 * 86400 < ttl < 2.8 * 86400


# ------------------------------------------------------------------ T3
def test_t3_ui_renders_six_cards_with_stale_and_fallback():
    now = time.time()
    items = {s: {"quote": {"value": 100.0, "ref": 99.0, "change": 1.0, "pct": 1.01, "ts": now}, "spark": [99.5, 100.0]}
             for s in IC.SYMBOLS}
    items["VN30"]["quote"]["ts"] = now - 500
    items["HNXINDEX"] = {"quote": None, "spark": []}
    out = IC.cards_html(items, now=now)
    assert out.count('class="idx-card"') == 6
    assert "Chỉ số VNINDEX" in out and "Hợp đồng tương lai VN30F1M" in out
    assert out.count("⚠️ cũ") == 2 and "chưa có dữ liệu" in out and "+1.00 / +1.01%" in out
    fb = IC.cards_html(None)
    assert "Redis đang lỗi" in fb


def test_t3_read_from_redis_via_reader(settings):
    feed = IndexFeed(settings, FakeRedis(), providers=[Fake("VIETCAP", {s: (2.0, 1.0) for s in SYMS})])
    feed.backfill()
    feed.cycle()

    class Reader:
        r, u = feed.r, {"cache_ttl_seconds": 1.5}

        def _cached(self, key, ttl, fn):
            return fn()
    items = IC.read(Reader())
    assert all(items[s]["quote"]["value"] == 2.0 and items[s]["spark"] for s in SYMS)
    assert IC.cards_html(items).count("⚠️ cũ") == 0


# ------------------------------------------------------------------ T4
def test_t4_provider_down_circuit_breaker_no_exception(settings):
    ent = Fake("ENTRADE", fail=True)
    vci = Fake("VIETCAP", {s: (2.0, 1.0) for s in SYMS})
    feed = IndexFeed(settings, FakeRedis(), providers=[ent, vci])
    for _ in range(5):
        q = feed.cycle()
        assert len(q) == 6 and q["VNINDEX"].source == "VIETCAP"
    assert feed.providers[0]["cb"].state == OPEN
    calls = ent.calls
    feed.cycle()
    assert ent.calls == calls   # OPEN -> không gọi nữa
    assert feed.health()["providers"]["ENTRADE"]["circuit"] == OPEN


def test_t4_sparse_failures_still_open_with_long_window(settings):
    ent = Fake("ENTRADE", fail=True)
    t = [0.0]
    feed = IndexFeed(settings, FakeRedis(), providers=[ent, Fake("VIETCAP", {s: (2.0, 1.0) for s in SYMS})],
                     mono=lambda: t[0])
    for _ in range(3):   # 1 lỗi / 30s (limiter thưa) vẫn phải mở circuit nhờ window 600s
        feed.cycle()
        t[0] += 30
    assert feed.providers[0]["cb"].state == OPEN


def test_t4_all_down_and_redis_down_no_exception(settings, caplog):
    feed = IndexFeed(settings, FakeRedis(fail=True), providers=[Fake("VIETCAP", fail=True)])
    assert feed.cycle() == {}
    feed.backfill()
    feed.write_health()
    text = caplog.text
    assert "ERR-IDX-002" in text and "ERR-IDX-004" in text


def test_t1_provider_disabled_by_config_is_skipped(settings):
    import copy
    s = copy.deepcopy(settings)
    s.provider_settings.setdefault("ENTRADE", {})["enabled"] = False
    feed = IndexFeed(s, FakeRedis())
    assert "ENTRADE" not in [e["p"].name for e in feed.providers]


def test_t1_repo_config_disables_entrade():
    s = common.load()
    assert s.provider_settings["ENTRADE"]["enabled"] is False
