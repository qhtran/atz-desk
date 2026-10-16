"""Module 4 - Live Position Monitor. Chạy trong container (cần Redis thật):

docker compose run --rm --no-deps -v ./tests:/app/tests -v ./pytest.ini:/app/pytest.ini position-monitor pytest -q -s tests/test_position_monitor.py
T1-T3 dùng Redis DB 13 (flush) + SQLite tạm. Integration: quote thật (DB 0) đọc-only, group + stream signal riêng
(test:pos:*), xoá sau khi chạy -> KHÔNG gửi alert thật.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
from datetime import datetime

import pytest
import redis

from position_monitor import config, store
from position_monitor.health import check
from position_monitor.log import TZ
from position_monitor.monitor import Monitor
from position_monitor.pnl import PnlError, calc

LABEL = re.compile(r"^\[DBG-\d{8}-\d{4}-POS-([A-Z]+)\]( (ERR-[A-Z]+-\d{3}))? (\{.*\})$")
TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://redis:6379/13")
SIG_FIELDS = {"signal_id", "user_id", "symbol", "timestamp", "filter_name", "direction", "price", "reason", "confidence"}


def entries(caplog):
    out = []
    for rec in caplog.records:
        if rec.name != "position_monitor":
            continue
        line = rec.getMessage()
        m = LABEL.match(line)
        assert m, f"log sai format label: {line}"
        d = json.loads(m.group(4))
        for k in ("debug_label", "error_code", "module", "symbol", "user_id", "latency_ms", "message"):
            assert k in d, (k, line)
        assert d["module"] == "POS" and d["error_code"] == m.group(3)
        out.append((m.group(1), d, line))
    return out


@pytest.fixture(autouse=True)
def _logs(caplog):
    caplog.set_level(logging.DEBUG, logger="position_monitor")


@pytest.fixture
def r():
    c = redis.Redis.from_url(TEST_URL, decode_responses=True)
    try:
        c.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("không có Redis")
    c.flushdb()
    yield c
    c.flushdb()


@pytest.fixture
def db(tmp_path):
    conn = store.open_db(str(tmp_path / "signals.db"))
    conn.execute("INSERT INTO users (id, username, created_at) VALUES (3, 'akadmin', '2026-10-16')")
    conn.commit()
    yield conn
    conn.close()


class Clock:
    def __init__(self):
        self.t = time.time()

    def __call__(self):
        return self.t


def make(r, db, clock, url=TEST_URL, **kw):
    cfg = copy.deepcopy(config.load())
    cfg["redis"]["url"] = url
    pm = cfg["position_monitor"]
    pm["consumer"]["group"] = kw.get("group", "pos-test")
    pm["consumer"]["block_ms"] = 100
    pm["alert"]["stream"] = kw.get("signals", "stream:signals")
    pm["live"]["key"] = kw.get("live", "pos:live:{user_id}")
    pm["health"]["key"] = kw.get("health", "pos:health")
    if "stream" in kw:
        pm["consumer"]["stream"] = kw["stream"]
    return Monitor(cfg, r=r, db=db, clock=clock)


def healthy_ingest(r, clock, mode="live"):
    r.set("ingest:health", json.dumps({"epoch": clock(), "mode": mode}))


def quote(clock, price, symbol="FPT", age=0, stale=False):
    ts = datetime.fromtimestamp(clock() - age, TZ).isoformat(timespec="seconds")
    return {"symbol": symbol, "timestamp": ts, "price": str(price), "source": "kbs", "stale": str(stale)}


def signals(r, stream="stream:signals"):
    return [f for _i, f in r.xrange(stream)]


# ---------------------------------------------------------------- T1 P&L
def test_t1_pnl_correct(r, db, caplog):
    assert calc(58600, 100, 60000).pnl == 140000.0
    assert calc(58600, 100, 60000).pnl_pct == pytest.approx(2.3891, abs=1e-4)
    assert calc(50000, 200, 45000).pnl == -1_000_000.0
    assert calc(50000, 200, 45000).pnl_pct == -10.0
    for bad in ((0, 100, 1), (100, -1, 1), (100, 1, None), (100, 1, "x")):
        with pytest.raises(PnlError):
            calc(*bad)
    clock = Clock()
    healthy_ingest(r, clock)
    pid = store.add(db, 3, "fpt", 100, 58600, stop_loss=55000, take_profit=65000)
    m = make(r, db, clock)
    m.reload(force=True)
    r.set("quote:FPT", json.dumps(quote(clock, 60000)))
    [s] = m.sweep()
    assert (s["pnl"], s["pnl_pct"], s["stale"], s["alerts"]) == (140000.0, pytest.approx(2.3891, abs=1e-4), False, [])
    live = json.loads(r.hget("pos:live:3", str(pid)))
    assert live["pnl"] == 140000.0 and live["market_value"] == 6_000_000.0
    # dữ liệu vị thế hỏng -> ERR-POS-002, không crash
    m.positions[0]["entry_price"] = 0
    m.sweep()
    errs = [l for a, d, l in entries(caplog) if d["error_code"] == "ERR-POS-002"]
    assert errs
    print("\nT1 log:", errs[0])


# ---------------------------------------------------------------- T2 SL/TP 1 lần
def test_t2_sl_tp_trigger_once(r, db, caplog):
    clock = Clock()
    healthy_ingest(r, clock)
    sl_id = store.add(db, 3, "FPT", 100, 58600, stop_loss=55000)
    tp_id = store.add(db, 3, "VNM", 10, 60000, take_profit=65000)
    m = make(r, db, clock)
    m.pm["volatility"]["enabled"] = False
    m.reload(force=True)
    for px_fpt, px_vnm in ((54900, 65100), (54000, 66000), (53000, 67000)):
        clock.t += 5
        r.set("quote:FPT", json.dumps(quote(clock, px_fpt)))
        r.set("quote:VNM", json.dumps(quote(clock, px_vnm, "VNM")))
        m.sweep()
    sigs = signals(r)
    assert len(sigs) == 2, sigs
    by = {s["filter_name"]: s for s in sigs}
    assert set(by) == {"pos_stop_loss", "pos_take_profit"}
    for s in sigs:
        assert set(s) == SIG_FIELDS and s["user_id"] == "3" and s["direction"] == "SELL"
    assert by["pos_stop_loss"]["symbol"] == "FPT" and float(by["pos_stop_loss"]["price"]) == 54900
    # restart (monitor mới) vẫn không bắn lại - dedup bền trong SQLite
    m2 = make(r, db, clock, group="pos-test2")
    m2.pm["volatility"]["enabled"] = False
    m2.reload(force=True)
    m2.sweep()
    assert len(signals(r)) == 2
    # rearm -> bắn lại đúng 1 lần
    store.rearm(db, sl_id)
    m2.reload(force=True)
    m2.sweep(); m2.sweep()
    assert len(signals(r)) == 3
    # publish lỗi -> trả lại trạng thái, không mất cảnh báo
    store.rearm(db, tp_id)
    m2.reload(force=True)
    m2.pm["alert"]["stream"] = "wrongtype"
    r.set("wrongtype", "x")
    m2.sweep()
    assert db.execute("SELECT tp_hit_at FROM positions WHERE id=?", (tp_id,)).fetchone()[0] is None
    m2.pm["alert"]["stream"] = "stream:signals"
    m2.reload(force=True)
    m2.sweep()
    assert len(signals(r)) == 4
    pub = [l for a, d, l in entries(caplog) if a == "ALERT" and "published" in d["message"]]
    print("\nT2 log:", pub[0])


def test_t2b_volatility_dedup(r, db, caplog):
    clock = Clock()
    healthy_ingest(r, clock)
    store.add(db, 3, "HPG", 1000, 30000)
    m = make(r, db, clock)
    m.reload(force=True)
    for px in (30000, 30300, 31000, 31200, 31500):
        clock.t += 30
        healthy_ingest(r, clock)
        r.set("quote:HPG", json.dumps(quote(clock, px, "HPG")))
        m.sweep()
    sigs = signals(r)
    assert len(sigs) == 1 and sigs[0]["filter_name"] == "pos_volatility" and sigs[0]["direction"] == "BUY"
    assert [l for a, d, l in entries(caplog) if a == "DEDUP"]


# ---------------------------------------------------------------- T3 stale
@pytest.mark.parametrize("case", ["old_quote", "flag", "ingest_degraded", "ingest_missing"])
def test_t3_stale_no_alert(r, db, caplog, case):
    clock = Clock()
    healthy_ingest(r, clock, "degraded" if case == "ingest_degraded" else "live")
    if case == "ingest_missing":
        r.delete("ingest:health")
    pid = store.add(db, 3, "FPT", 100, 58600, stop_loss=55000, take_profit=65000)
    m = make(r, db, clock)
    m.reload(force=True)
    q = quote(clock, 50000, age=600 if case == "old_quote" else 0, stale=case == "flag")
    r.set("quote:FPT", json.dumps(q))
    [s] = m.sweep()
    m.sweep()
    assert s["stale"] is True and s["stale_reason"]
    assert s["pnl"] == -860000.0            # vẫn tính P&L nhưng gắn stale
    assert signals(r) == []
    assert db.execute("SELECT sl_hit_at FROM positions WHERE id=?", (pid,)).fetchone()[0] is None
    assert json.loads(r.hget("pos:live:3", str(pid)))["stale"] is True
    stale = [l for a, d, l in entries(caplog) if d["error_code"] == "ERR-POS-001"]
    assert len(stale) == 1                 # log giới hạn 1 lần/mã/5 phút
    if case == "old_quote":
        print("\nT3 log:", stale[0])
    # dữ liệu tươi trở lại -> cảnh báo SL bình thường
    healthy_ingest(r, clock)
    r.set("quote:FPT", json.dumps(quote(clock, 50000)))
    m.sweep()
    assert len(signals(r)) == 1


def test_stream_event_and_health(r, db):
    clock = Clock()
    healthy_ingest(r, clock)
    store.add(db, 3, "FPT", 100, 58600, stop_loss=55000)
    m = make(r, db, clock)
    m.pm["sweep_seconds"] = 10**9
    m._last_sweep = clock()
    m.reload(force=True)
    r.xadd("stream:quotes", quote(clock, 54000))
    r.xadd("stream:quotes", quote(clock, 70000, "VNM"))   # không có vị thế -> bỏ qua
    assert m.step() == 2
    assert len(signals(r)) == 1
    assert r.xinfo_groups("stream:quotes")[0]["pending"] == 0
    m.write_health()
    cfg = copy.deepcopy(config.load()); cfg["redis"]["url"] = TEST_URL
    ok, info = check(cfg, r)
    assert ok and info["position_monitor_health"]["open_positions"] == 1


# ---------------------------------------------------------------- Integration (Redis thật)
def test_integration_real_redis(tmp_path, caplog):
    url = os.environ.get("REDIS_LIVE_URL", "redis://redis:6379/0")
    live = redis.Redis.from_url(url, decode_responses=True)
    try:
        live.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("không có Redis")
    sym = "FPT"
    raw = live.get(f"quote:{sym}")
    if not raw:
        pytest.skip("chưa có quote thật")
    conn = store.open_db(str(tmp_path / "it.db"))
    conn.execute("INSERT INTO users (id, username, created_at) VALUES (3, 'it', '2026-10-16')"); conn.commit()
    px = json.loads(raw)["price"]
    store.add(conn, 3, sym, 100, px * 0.9, stop_loss=px * 0.5)
    tag = f"test:pos:{int(time.time())}"
    m = make(live, conn, time.time, url=url, group=tag + ":group", signals=tag + ":signals",
             live=tag + ":live:{user_id}", health=tag + ":health")
    try:
        m.reload(force=True)
        t0 = time.monotonic()
        [s] = m.sweep()
        ms = int((time.monotonic() - t0) * 1000)
        n = m.step()
        assert s["price"] == px and s["pnl"] == pytest.approx((px - px * 0.9) * 100, rel=1e-6)
        assert live.xlen(tag + ":signals") == 0 if live.exists(tag + ":signals") else True
        print(f"\nIT: quote thật {sym}={px} pnl={s['pnl']} pnl_pct={s['pnl_pct']} stale={s['stale']} ({s['stale_reason']}) sweep={ms}ms step_events={n}")
    finally:
        try:
            live.xgroup_destroy("stream:quotes", tag + ":group")
        except redis.exceptions.ResponseError:
            pass
        live.delete(tag + ":signals", tag + ":live:3", tag + ":health")
        assert not live.keys(tag + "*")
        assert tag + ":group" not in [g["name"] for g in live.xinfo_groups("stream:quotes")]
