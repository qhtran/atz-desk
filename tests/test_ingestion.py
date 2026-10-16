"""Module 1 - Ingestion Service. Chạy trong container ingestion (cần Redis thật + mạng tới KBS).

docker compose run --rm -v ./tests:/app/tests ingestion pytest -q tests/test_ingestion.py
Dùng Redis DB riêng (REDIS_TEST_URL, mặc định db 15) để không đụng dữ liệu live.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
from datetime import datetime

import pandas as pd
import pytest
import redis

from ingestion import config
from ingestion.health import check
from ingestion.normalizer import Quote
from ingestion.orchestrator import Orchestrator
from ingestion.rate_limiter import TokenBucket
from ingestion.store import RedisStore

SYMBOLS = ["VNM", "VCB", "HPG", "FPT", "MWG", "TCB", "SSI", "VHM", "MBB", "ACB"]
FIELDS = ["symbol", "exchange", "timestamp", "price", "change", "change_pct", "volume", "open",
          "high", "low", "ref_price", "source", "batch_id", "latency_ms"]


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(0.0, seconds)


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("REDIS_URL", os.environ.get("REDIS_TEST_URL", "redis://redis:6379/15"))
    return config.load()


@pytest.fixture
def store(settings):
    s = RedisStore(settings)
    try:
        s.r.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("Redis không truy cập được")
    s.r.flushdb()
    yield s
    s.r.flushdb()


@pytest.fixture(autouse=True)
def _logs(caplog):
    caplog.set_level(logging.INFO, logger="ingestion")


LABEL = re.compile(r"^\[DBG-\d{8}-\d{4}-INGEST-([A-Z]+)\]( (ERR-[A-Z]+-\d{3}))? (\{.*\})$")


def entries(caplog):
    """Parse mọi dòng log: kiểm format label + JSON structured fields."""
    out = []
    for rec in caplog.records:
        if rec.name != "ingestion":
            continue
        line = rec.getMessage()
        m = LABEL.match(line)
        assert m, f"log thiếu debug label đúng format: {line}"
        data = json.loads(m.group(4))
        for key in ("debug_label", "error_code", "module", "symbol", "user_id", "latency_ms", "message"):
            assert key in data, (key, line)
        assert data["module"] == "INGEST" and data["error_code"] == m.group(3)
        out.append((m.group(1), data, line))
    return out


def find(caplog, action, text="", code=None):
    return [line for act, data, line in entries(caplog)
            if act == action and text in data["message"] and (code is None or data["error_code"] == code)]


def board(symbols, price=10000.0):
    return pd.DataFrame([{"symbol": s, "exchange": "HOSE", "reference_price": price, "open_price": price,
                          "high_price": price * 1.02, "low_price": price * 0.98,
                          "close_price": price * 1.01} for s in symbols])


def failing(counter, name):
    def fetch(symbols):
        counter[name] = counter.get(name, 0) + 1
        raise ConnectionError(f"{name} simulated outage")
    return fetch


def test_t1_real_kbs_batch_normalized_and_cached(settings, store, caplog):
    orch = Orchestrator(settings, store)   # fetcher thật: vnstock price_board source=kbs
    quotes = orch.run_cycle(SYMBOLS)
    assert {q.symbol for q in quotes} == set(SYMBOLS)
    for q in quotes:
        d = q.to_dict()
        assert list(d)[: len(FIELDS)] == FIELDS
        assert q.source == "kbs" and not q.stale and q.price > 0
        assert datetime.fromisoformat(q.timestamp).utcoffset().total_seconds() == 7 * 3600
        assert q.batch_id.startswith("b_") and q.latency_ms >= 0
        cached = json.loads(store.r.get(f"quote:{q.symbol}"))
        assert cached["price"] == q.price and 0 < store.r.ttl(f"quote:{q.symbol}") <= settings.quote_ttl_seconds
    assert store.r.xlen(settings.stream) == len(SYMBOLS)
    # change detector: chạy lại cùng dữ liệu nếu giá đứng yên thì không publish thêm (không assert cứng vì giá live).
    ok = find(caplog, "FETCH", "source=KBS ok")
    assert ok and json.loads(ok[0].split(" ", 1)[1])["latency_ms"] >= 0
    assert find(caplog, "REDIS", "published stream=stream:quotes")
    print("\n".join(line for _, _, line in entries(caplog)))
    print("sample:", json.dumps(quotes[0].to_dict(), ensure_ascii=False))


def test_t2_kbs_fails_5_times_circuit_opens_switch_to_vci(settings, store, caplog):
    clock, calls = FakeClock(), {}
    orch = Orchestrator(settings, store, fetchers={"KBS": failing(calls, "KBS"), "VCI": lambda s: board(s)},
                        clock=clock, sleep=clock.sleep)
    kbs = orch.sources[0]
    for i in range(5):
        quotes = orch.run_cycle(SYMBOLS)
        assert all(q.source == "vci" for q in quotes) and len(quotes) == 10
    assert kbs.breaker.state == "OPEN"
    attempts = calls["KBS"]
    quotes = orch.run_cycle(SYMBOLS)              # breaker OPEN: KBS không bị gọi nữa
    assert calls["KBS"] == attempts and all(q.source == "vci" for q in quotes)
    clock.sleep(settings.recovery_timeout_seconds)
    assert kbs.breaker.state == "HALF_OPEN"
    orch.sources[0].fetch_fn = lambda s: board(s)  # KBS hồi phục -> thử lại -> CLOSED
    assert all(q.source == "kbs" for q in orch.run_cycle(SYMBOLS))
    assert kbs.breaker.state == "CLOSED"
    assert find(caplog, "CB", "source=KBS failure 5/5")
    assert find(caplog, "CB", "source=KBS CLOSED->OPEN", code="ERR-INGEST-002")
    assert find(caplog, "CB", "source=KBS OPEN->HALF_OPEN")
    switch = find(caplog, "FETCH", "Circuit Open for KBS, switching to next source", code="ERR-INGEST-002")
    assert switch and '"circuit_state": "OPEN"' in switch[0]
    print("\n".join(line for act, _, line in entries(caplog) if act == "CB" or "ERR-INGEST-002" in line))


def test_t3_rate_limiter_at_most_380_per_minute(caplog):
    clock = FakeClock()
    bucket = TokenBucket(380, 10, 0.2, clock=clock, sleep=clock.sleep)
    stamps = []
    start = clock()
    while clock() - start < 180:                   # bơm liên tục trong 3 phút giả lập
        bucket.acquire("TEST")
        stamps.append(clock())
    # mọi cửa sổ 60s trượt
    worst, j = 0, 0
    for i, t in enumerate(stamps):
        while stamps[j] <= t - 60:
            j += 1
        worst = max(worst, i - j + 1)
    first_minute = sum(1 for t in stamps if t < start + 60)
    print(f"first_minute={first_minute} worst_60s_window={worst} throttled={bucket.throttled}")
    assert worst <= 380 and first_minute <= 380
    assert find(caplog, "RATE", "near-limit")
    assert find(caplog, "RATE", "throttle", code="ERR-INGEST-001")
    assert bucket.current_rpm() <= 380
    lines = [l for _, _, l in entries(caplog)]
    print(next(l for l in lines if "near-limit" in l)); print(next(l for l in lines if "throttle" in l))


def test_t4_both_down_degraded_serves_stale_cache(settings, store, caplog):
    clock, calls = FakeClock(), {}
    old = [Quote(symbol=s, exchange="HOSE", timestamp="2026-10-16T10:07:00+07:00", price=50000.0, change=0.0,
                 change_pct=0.0, volume=None, open=50000.0, high=50000.0, low=50000.0, ref_price=50000.0,
                 source="kbs", batch_id="b_old", latency_ms=1) for s in SYMBOLS]
    store.save(old)
    orch = Orchestrator(settings, store, fetchers={"KBS": failing(calls, "KBS"), "VCI": failing(calls, "VCI")},
                        clock=clock, sleep=clock.sleep)
    normal = orch.interval()
    quotes = orch.run_cycle(SYMBOLS)
    assert len(quotes) == 10 and all(q.stale and q.batch_id == "b_old" and q.price == 50000.0 for q in quotes)
    assert orch.degraded and orch.interval() > normal
    assert orch.health()["mode"] == "degraded"
    for _ in range(6):                             # tiếp tục không crash, breaker mở cả hai
        assert len(orch.run_cycle(SYMBOLS)) == 10
    assert {a.breaker.state for a in orch.sources} == {"OPEN"}
    # Redis cũng lỗi -> vẫn không crash
    orch.store = RedisStore(dataclasses.replace(settings, redis_url="redis://127.0.0.1:1/0"))
    assert orch.run_cycle(SYMBOLS) == []
    assert find(caplog, "DEGRADE", "entering degraded mode", code="ERR-INGEST-004")
    assert find(caplog, "DEGRADE", "stale=True", code="ERR-INGEST-004")
    assert find(caplog, "FETCH", "Circuit Open for VCI", code="ERR-INGEST-003")
    assert find(caplog, "DEGRADE", "cache read failed", code="ERR-SYS-001")
    lines = [l for act, _, l in entries(caplog) if act == "DEGRADE" or "ERR-INGEST-003" in l]
    print("\n".join(lines[:3] + lines[-3:]))


def test_normalize_and_redis_write_error_codes(settings, store, caplog):
    orch = Orchestrator(settings, store, fetchers={"KBS": lambda s: pd.concat([board(s), pd.DataFrame([{"symbol": "BAD"}])]),
                                                   "VCI": lambda s: board(s)})
    assert len(orch.run_cycle(SYMBOLS)) == 10
    assert find(caplog, "NORMALIZE", "normalize failed", code="ERR-INGEST-005")
    orch.store = RedisStore(dataclasses.replace(settings, redis_url="redis://127.0.0.1:1/0"))
    orch.run_cycle(SYMBOLS)                        # Redis chết khi ghi -> không crash
    assert find(caplog, "REDIS", "redis write failed (ERR-INGEST-006)", code="ERR-SYS-001")


def test_timeout_error_code(settings, store, caplog):
    import time as _t
    slow = dataclasses.replace(settings, request_timeout_seconds=0.2, retries=0)
    orch = Orchestrator(slow, store, fetchers={"KBS": lambda s: _t.sleep(1), "VCI": lambda s: board(s)})
    assert all(q.source == "vci" for q in orch.run_cycle(SYMBOLS[:2]))
    assert find(caplog, "FETCH", "TimeoutError", code="ERR-INGEST-007")


def test_health_check_ok(settings, store, caplog):
    orch = Orchestrator(settings, store, fetchers={"KBS": lambda s: board(s), "VCI": lambda s: board(s)})
    orch.run_cycle(SYMBOLS)
    store.write_health(orch.health())
    ok, info = check(settings, store)
    ing = info["ingestion_health"]
    assert ok and ing["mode"] == "live" and ing["breakers"] == {"KBS": "CLOSED", "VCI": "CLOSED"}
    assert ing["last_successful_fetch"] and ing["current_rpm"] >= 1
    assert info["redis_health"]["ping"] == "PONG" and info["redis_health"]["used_memory_human"]
    print(json.dumps(info, ensure_ascii=False)[:600])
    store.r.delete(settings.health_key)
    assert check(settings, store)[0] is False
