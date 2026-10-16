"""Module 2 - Streaming Filter Runner. Chạy trong container filter-runner (cần Redis thật).

docker compose run --rm --no-deps -v ./tests:/app/tests -v ./pytest.ini:/app/pytest.ini filter-runner pytest -q -s tests/test_filter_runner.py
T1-T3 dùng Redis DB 14 (flush). Integration dùng stream:quotes thật (DB 0) với group riêng, xoá sau khi chạy.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import pytest
import redis

from filter_runner import config
from filter_runner.contracts import Signal
from filter_runner.health import check
from filter_runner.history import HistoryCache
from filter_runner.registry import FilterRegistry
from filter_runner.runner import FilterRunner
from filters import load_registry
from filters.base import FilterSpec, hit

FIELDS = ["signal_id", "user_id", "symbol", "timestamp", "filter_name", "direction", "price", "reason", "confidence"]
LABEL = re.compile(r"^\[DBG-\d{8}-\d{4}-FILTER-([A-Z]+)\]( (ERR-[A-Z]+-\d{3}))? (\{.*\})$")
TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://redis:6379/14")


def entries(caplog):
    out = []
    for rec in caplog.records:
        if rec.name != "filter_runner":
            continue
        line = rec.getMessage()
        m = LABEL.match(line)
        assert m, f"log sai format label: {line}"
        data = json.loads(m.group(4))
        for key in ("debug_label", "error_code", "module", "symbol", "user_id", "latency_ms", "message"):
            assert key in data, (key, line)
        assert data["module"] == "FILTER" and data["error_code"] == m.group(3)
        out.append((m.group(1), data, line))
    return out


def find(caplog, action, text="", code=None):
    return [l for a, d, l in entries(caplog) if a == action and text in d["message"] and (code is None or d["error_code"] == code)]


@pytest.fixture(autouse=True)
def _logs(caplog):
    caplog.set_level(logging.INFO, logger="filter_runner")


@pytest.fixture
def r():
    client = redis.Redis.from_url(TEST_URL, decode_responses=True)
    try:
        client.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("không có Redis")
    client.flushdb()
    yield client
    client.flushdb()


def falling_bars(days=120, start=80.0):
    """Nến giảm đều -> RSI rất thấp (quá bán) -> filter rsi trả 'mua'."""
    today = datetime.now().date()
    rows, price = [], start
    for i in range(days):
        price *= 0.985
        day = today - timedelta(days=days - i)
        rows.append({"time": f"{day} 07:00:00+07:00", "open": price * 1.01, "high": price * 1.015,
                     "low": price * 0.995, "close": price, "volume": 1_000_000 + i})
    frame = pd.DataFrame(rows)
    frame["_day"] = pd.to_datetime(frame["time"]).dt.date
    return frame


class Plans:
    def __init__(self, plans):
        self._plans = plans

    def plans(self):
        return self._plans


def make_runner(r, plans, modules=None, **overrides):
    cfg = copy.deepcopy(config.load())
    cfg["redis"]["url"] = TEST_URL
    fr = cfg["filter_runner"]
    fr["consumer"]["group"] = "fr-test"
    for path, value in overrides.items():
        section, key = path.split(".")
        fr[section][key] = value
    bars = falling_bars()
    history = HistoryCache(400, 600, 0.001, loaders=(lambda s, start: bars, lambda: None, lambda s, k: pd.DataFrame()))
    return FilterRunner(cfg, r=r, registry=FilterRegistry(modules or load_registry()), history=history,
                        resolver=Plans(plans)), bars


def quote_for(bars, symbol="VNM"):
    px = float(bars["close"].iloc[-1]) * 0.98 * 1000   # VND, tiếp tục giảm
    return {"symbol": symbol, "exchange": "HOSE", "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "price": str(px), "open": str(px), "high": str(px), "low": str(px), "ref_price": str(px),
            "volume": "", "source": "kbs", "batch_id": "b_test", "latency_ms": "100", "stale": "False"}


def fake_module(name, fn):
    class M:
        FILTER = FilterSpec(name=name, label=name, description="test", group="test", params=())
        evaluate = staticmethod(fn)
    return M


def test_t1_quote_runs_existing_filter_and_emits_contract_signal(r, caplog):
    runner, bars = make_runner(r, {"3": [{"kind": "filter", "name": "rsi", "params": {}},
                                         {"kind": "filter", "name": "macd", "params": {}}]})
    assert {"rsi", "macd", "ma", "volume"} <= set(runner.registry.names())
    signals = runner.process_quote(quote_for(bars))
    assert signals and signals[0].filter_name == "rsi" and signals[0].direction == "BUY"
    raw = r.xrange("stream:signals")
    assert len(raw) == len(signals)
    fields = raw[0][1]
    assert list(fields) == FIELDS and list(Signal.__dataclass_fields__) == FIELDS
    assert fields["signal_id"].startswith("sig_") and fields["user_id"] == "3" and fields["symbol"] == "VNM"
    assert datetime.fromisoformat(fields["timestamp"]).utcoffset().total_seconds() == 7 * 3600
    assert 0 <= float(fields["confidence"]) <= 1 and float(fields["price"]) > 0 and "RSI" in fields["reason"]
    assert find(caplog, "SIGNAL", "published BUY rsi")
    print("signal:", json.dumps(fields, ensure_ascii=False))
    print(find(caplog, "SIGNAL", "published")[0])


def test_t2_isolation_timeout_and_disabled(r, caplog):
    def boom(bars, params=None):
        raise ZeroDivisionError("bug in filter")

    def slow(bars, params=None):
        time.sleep(1.5)
        return hit("mua", "slow", {})

    modules = dict(load_registry())
    modules["boom"], modules["slow"] = fake_module("boom", boom), fake_module("slow", slow)
    plan = {"3": [{"kind": "filter", "name": n, "params": {}} for n in ("boom", "slow", "rsi")]}
    runner, bars = make_runner(r, plan, modules, **{"evaluator.timeout_seconds": 0.3,
                                                    "filter_circuit.failure_threshold": 2})
    first = runner.process_quote(quote_for(bars, "VNM"))
    assert [s.filter_name for s in first] == ["rsi"]               # rsi vẫn chạy dù boom/slow lỗi
    assert find(caplog, "EVAL", "filter exception isolated: ZeroDivisionError", code="ERR-FILTER-002")
    assert find(caplog, "EVAL", "filter evaluate timeout", code="ERR-FILTER-001")
    runner.process_quote(quote_for(bars, "HPG"))                   # lỗi lần 2 -> disable
    assert find(caplog, "CIRCUIT", "filter disabled", code="ERR-FILTER-003")
    third = runner.process_quote(quote_for(bars, "FPT"))
    assert find(caplog, "EVAL", "skip: filter temporarily disabled", code="ERR-FILTER-003")
    assert [s.filter_name for s in third] == ["rsi"]
    beat = runner.health()
    assert beat["disabled_filters"] == 2 and set(beat["disabled_filter_names"]) == {"boom", "slow"}
    assert beat["signals_per_minute"] == 3
    for code in ("ERR-FILTER-002", "ERR-FILTER-001", "ERR-FILTER-003"):
        print(next(l for _, _, l in entries(caplog) if code in l)[:330])


def test_t3_dedup_suppresses_duplicate_within_window(r, caplog):
    runner, bars = make_runner(r, {"3": [{"kind": "filter", "name": "rsi", "params": {}}]})
    q = quote_for(bars)
    assert len(runner.process_quote(q)) == 1
    assert runner.process_quote(q) == []
    assert r.xlen("stream:signals") == 1
    ttl = r.ttl("dedup:3:VNM:rsi:BUY")
    assert 590 <= ttl <= 600
    assert find(caplog, "DEDUP", "duplicate suppressed within 600s")
    # Redis lỗi khi dedup -> ERR-FILTER-004, fail-closed (không publish)
    runner.dedup.r = redis.Redis.from_url("redis://127.0.0.1:1/0")
    assert runner.process_quote(quote_for(bars, "HPG")) == []
    assert find(caplog, "DEDUP", "dedup check failed", code="ERR-FILTER-004")
    print(find(caplog, "DEDUP", "duplicate")[0][:300]); print(find(caplog, "DEDUP", "failed")[0][:300])


def test_consumer_group_ack_pending_recovery_and_backpressure(r, caplog):
    runner, bars = make_runner(r, {"3": [{"kind": "filter", "name": "rsi", "params": {}}]},
                               **{"backpressure.lag_threshold": 2, "consumer.claim_min_idle_ms": 0})
    for sym in ("VNM", "VNM", "VNM", "HPG", "HPG"):
        r.xadd("stream:quotes", quote_for(bars, sym))
    # consumer "chết": đọc mà không ack
    r.xreadgroup("fr-test", "dead", {"stream:quotes": ">"}, count=2)
    assert runner.step() == 2                                   # XAUTOCLAIM lấy lại 2 message pending
    assert find(caplog, "CONSUME", "recovered pending messages=2")
    assert runner.step() == 3                                   # 3 còn lại, lag>ngưỡng -> coalesce
    assert r.xpending("stream:quotes", "fr-test")["pending"] == 0
    assert runner.metrics["acked"] == 5
    print("\n".join(l[:260] for a, _, l in entries(caplog) if a in ("CONSUME", "BACKPRESSURE")))


def test_health_check_ok(r):
    runner, bars = make_runner(r, {"3": [{"kind": "filter", "name": "rsi", "params": {}}]})
    runner.process_quote(quote_for(bars))
    cfg = copy.deepcopy(config.load())
    cfg["redis"]["url"] = TEST_URL
    runner.write_health()
    ok, info = check(cfg, r)
    beat = info["filter_runner_health"]
    assert ok and beat["signals_per_minute"] == 1 and beat["disabled_filters"] == 0
    print(json.dumps(info, ensure_ascii=False)[:400])


def test_integration_real_ingestion_stream(caplog):
    """Quote thật do atz-ingestion ghi vào stream:quotes (DB 0) -> runner (history thật từ data/ohlcv) -> ack."""
    live = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    assert live.xlen("stream:quotes") > 0, "ingestion chưa ghi stream"
    cfg = copy.deepcopy(config.load())
    fr = cfg["filter_runner"]
    group = f"fr-it-{os.getpid()}"
    fr["consumer"].update({"group": group, "read_count": 200, "block_ms": 500})
    fr["publisher"]["stream"] = "stream:signals:it"
    fr["dedup"]["key"] = "dedup:it:{user_id}:{symbol}:{filter_name}:{direction}"
    fr["history"]["remote_fetch"] = False            # không tốn quota API trong test
    live.xgroup_create("stream:quotes", group, id="0")   # đọc lại từ đầu (đã có dữ liệu thật)
    try:
        runner = FilterRunner(cfg, r=live)
        n = runner.step()
        assert n > 0 and live.xpending("stream:quotes", group)["pending"] == 0
        assert runner.metrics["evaluations"] > 0
        assert find(caplog, "CONSUME", f"acked={n}")
        print(f"consumed={n} acked={runner.metrics['acked']} evaluations={runner.metrics['evaluations']} "
              f"signals={runner.metrics['signals']} duplicates={runner.metrics['duplicates']}")
        print(find(caplog, "CONSUME", "acked=")[0][:300])
    finally:
        live.xgroup_destroy("stream:quotes", group)
        live.delete("stream:signals:it", *live.keys("dedup:it:*"))
