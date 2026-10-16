"""Module 5 - UI Realtime. T1 bảng giá Redis + stale, T2 vị thế CRUD + cách ly, T3 thông báo/cài đặt, T4 Redis down.

Redis test: REDIS_TEST_URL (mặc định redis://redis:6379/12, flushdb). Không đụng data/signals.db.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta

import pytest
import redis

from position_monitor import store as pos_store
from storage.repository import ensure_user
from ui_realtime import config as ui_config
from ui_realtime import data
from ui_realtime.log import TZ

import os

TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://redis:6379/12")
LINE = re.compile(r"\[(DBG-\d{8}-\d{4}-UI-[A-Z-]+)\](?: (ERR-[A-Z]+-\d{3}))? (\{.*\})$")


@pytest.fixture(autouse=True)
def _logs(caplog):
    caplog.set_level(logging.DEBUG, logger="ui_realtime")


def ui_lines(caplog):
    out = []
    for rec in caplog.records:
        if rec.name != "ui_realtime":
            continue
        m = LINE.match(rec.getMessage())
        assert m, rec.getMessage()
        d = json.loads(m.group(3))
        assert d["debug_label"] == m.group(1) and d["module"] == "UI"
        out.append((m.group(1), m.group(2), d))
    return out


@pytest.fixture
def cfg(tmp_path):
    c = ui_config.load()
    c["redis"]["url"] = TEST_URL
    c["sqlite"]["path"] = str(tmp_path / "signals.db")
    return c


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
def conn(cfg):
    cn = data.open_db(cfg)
    yield cn
    cn.close()


def _quote(sym, price, age_s=1, stale=False):
    ts = (datetime.now(TZ) - timedelta(seconds=age_s)).isoformat(timespec="seconds")
    return json.dumps({"symbol": sym, "timestamp": ts, "price": price, "change": 100.0, "change_pct": 0.5, "open": price,
                       "high": price, "low": price, "ref_price": price - 100, "source": "kbs", "stale": stale})


# ---------------------------------------------------------------- T1
def test_t1_board_reads_redis_mget_cache_and_stale(cfg, r, caplog):
    r.set("quote:FPT", _quote("FPT", 58100))
    r.set("quote:VPB", _quote("VPB", 24400, age_s=600))          # cũ -> stale
    r.set("quote:ACB", _quote("ACB", 25000, stale=True))          # ingestion gắn cờ
    t = [0.0]
    rd = data.RedisReader(cfg, clock=lambda: t[0])
    q = rd.quotes()
    rows = {x["Mã"]: x for x in data.quote_rows(q, cfg["ui_realtime"]["quote_stale_seconds"])}
    assert rows["FPT"]["Giá"] == 58100 and not rows["FPT"]["_stale"] and rows["FPT"]["Trạng thái"] == "live"
    assert rows["VPB"]["_stale"] and rows["VPB"]["Trạng thái"] == "⚠️ cũ"
    assert rows["ACB"]["_stale"]
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", rows["FPT"]["Lúc"])
    calls = rd.stats["redis_calls"]
    for _ in range(50):                                          # 50 session trong 1.5s -> 0 lệnh Redis mới
        rd.quotes()
    assert rd.stats["redis_calls"] == calls and rd.stats["cache_hits"] >= 50
    r.set("quote:FPT", _quote("FPT", 59000))
    t[0] = 2.0                                                   # hết TTL cache -> đọc lại
    assert {x["symbol"]: x["price"] for x in rd.quotes()}["FPT"] == 59000


def test_t1_refresh_interval_trading_hours(cfg):
    mk = lambda h, m, d=16: datetime(2026, 10, d, h, m, tzinfo=TZ)  # noqa: E731  (16/10/2026 thứ 6)
    assert data.refresh_seconds(cfg, mk(9, 30)) == 3 and data.refresh_seconds(cfg, mk(14, 59)) == 3
    assert data.refresh_seconds(cfg, mk(12, 0)) == 30 and data.refresh_seconds(cfg, mk(15, 30)) == 30
    assert data.refresh_seconds(cfg, mk(10, 0, d=17)) == 30      # thứ 7


# ---------------------------------------------------------------- T2
def test_t2_positions_crud_and_isolation(cfg, conn, r, caplog):
    a, b = ensure_user(conn, "akadmin"), ensure_user(conn, "bob")
    pid = data.add_position(conn, a, "fpt", 100, 58.6, 55, 65, unit="k")
    p = data.list_positions(conn, a)[0]
    assert (p["symbol"], p["entry_price"], p["stop_loss"], p["take_profit"]) == ("FPT", 58600, 55000, 65000)
    with pytest.raises(data.UserError) as e:                     # cùng validation store.add (LONG)
        data.add_position(conn, a, "FPT", 100, 58600, sl=60000)
    assert e.value.code == "ERR-UI-001"
    with pytest.raises(data.UserError):
        data.add_position(conn, a, "FPT", 0, 58600)
    with pytest.raises(data.UserError):
        data.add_position(conn, a, "F P T!", 100, 58600)
    pos_store.mark_hit(conn, pid, "sl")
    data.update_levels(conn, a, pid, sl=56000)                   # đổi SL -> rearm SL, TP giữ
    p = data.list_positions(conn, a)[0]
    assert p["stop_loss"] == 56000 and p["sl_hit_at"] is None and p["take_profit"] == 65000
    with pytest.raises(data.UserError):
        data.update_levels(conn, a, pid, tp=50000)
    # cách ly: bob không thấy / sửa / đóng vị thế của akadmin
    assert data.list_positions(conn, b) == []
    for fn in (lambda: data.update_levels(conn, b, pid, sl=50000), lambda: data.close_position(conn, b, pid)):
        with pytest.raises(data.UserError) as e:
            fn()
        assert e.value.code == "ERR-UI-002"
    assert data.list_positions(conn, a)[0]["status"] == "open"
    # live P&L đọc đúng hash của user
    r.hset(f"pos:live:{a}", str(pid), json.dumps({"position_id": pid, "price": 60000, "pnl": 140000, "pnl_pct": 2.39}))
    r.hset(f"pos:live:{b}", "999", json.dumps({"position_id": 999, "pnl": 1}))
    rd = data.RedisReader(cfg)
    assert list(rd.live_positions(a)) == [pid] and rd.live_positions(a)[pid]["pnl"] == 140000
    assert data.close_position(conn, a, pid) and data.list_positions(conn, a) == []
    labels = [x[0].split("-UI-")[1] for x in ui_lines(caplog)]
    assert {"POS-ADD", "POS-SET", "POS-OWN", "POS-CLOSE"} <= set(labels)
    assert any(code == "ERR-UI-002" for _, code, _ in ui_lines(caplog))


# ---------------------------------------------------------------- T3
def test_t3_inapp_unread_and_isolation(cfg, r):
    for i, uid in enumerate(["3", "3", "4"]):
        r.lpush(f"inapp:{uid}", json.dumps({"signal_id": f"s{i}", "user_id": uid, "symbol": "FPT", "direction": "BUY",
                                            "timestamp": f"2026-10-16T13:0{i}:00+07:00", "filter_name": "rsi"}))
    r.lpush("inapp:3", json.dumps({"signal_id": "x", "user_id": "4", "symbol": "LEAK", "timestamp": "2026-10-16T14:00:00+07:00"}))
    rd = data.RedisReader(cfg)
    items = rd.inapp(3)
    assert [x["signal_id"] for x in items] == ["s1", "s0"]       # bỏ tin user khác lọt vào key
    assert rd.seen(3) == ""
    assert rd.mark_seen(3, max(x["timestamp"] for x in items))
    assert rd.seen(3) == "2026-10-16T13:01:00+07:00"
    assert rd.seen(4) == ""


def test_t3_settings_validate_and_save(cfg, conn, caplog):
    from alert_dispatcher.prefs import in_quiet, resolve
    from alert_dispatcher.store import get_user
    uid = ensure_user(conn, "akadmin")
    conn.execute("UPDATE users SET cai_dat_chung = ? WHERE id = ?", (json.dumps({"loai_nhan": ["mua"]}), uid)); conn.commit()
    for bad in [dict(telegram_chat_id="abc"), dict(email="x@"), dict(email="", email_bat=True),
                dict(quiet_start="22:00", quiet_end=""), dict(quiet_start="25:00", quiet_end="07:00")]:
        args = dict(telegram_chat_id="", telegram_bat=True, email="", email_bat=False, quiet_start="", quiet_end="") | bad
        with pytest.raises(data.UserError) as e:
            data.save_settings(conn, uid, **args)
        assert e.value.code == "ERR-UI-003"
    data.save_settings(conn, uid, "8505117958", True, "admin@atz.vn", True, "22:00", "07:00")
    s = data.get_settings(conn, uid)
    assert s == {"telegram_chat_id": "8505117958", "telegram_bat": True, "email": "admin@atz.vn", "email_bat": True,
                 "quiet_hours": {"start": "22:00", "end": "07:00"}}
    u = get_user(conn, str(uid))
    assert u["cai_dat_chung"]["loai_nhan"] == ["mua"]           # giữ key cũ
    p = resolve(u, {"direction": "BUY"})                         # Module 3 đọc được đúng
    assert p.channels == ["telegram", "email"] and in_quiet(p.quiet_hours, datetime(2026, 10, 16, 23, 0))
    data.save_settings(conn, uid, "", False, "admin@atz.vn", False, "", "")
    assert data.get_settings(conn, uid)["quiet_hours"] is None
    assert any(x[0].endswith("UI-SETTINGS") for x in ui_lines(caplog))


def test_t3_health_panel(cfg, r):
    import time
    now = time.time()
    r.set("ingest:health", json.dumps({"epoch": now, "mode": "live", "current_rpm": 20, "breakers": {"KBS": "CLOSED"}}))
    r.set("filter:health", json.dumps({"epoch": now - 500, "signals_per_minute": 1}))
    r.set("alert:health", json.dumps({"epoch": now, "channels": {"telegram": {"circuit": "closed"}}}))
    h = data.RedisReader(cfg).health()
    assert h["redis"]["ok"] and h["ingestion"]["ok"] and h["alert"]["ok"]
    assert not h["filter"]["ok"] and not h["position"]["ok"] and h["position"]["detail"] == "heartbeat missing"


# ---------------------------------------------------------------- T4
def test_t4_redis_down_fallback(cfg, caplog):
    cfg["redis"]["url"] = "redis://127.0.0.1:1/0"
    t = [0.0]
    rd = data.RedisReader(cfg, clock=lambda: t[0])
    assert rd.quotes() is None and rd.inapp(3) is None and rd.live_positions(3) is None
    assert not rd.available                                     # bỏ qua Redis 10s: không treo mỗi fragment
    calls = rd.stats["redis_calls"]
    rd.quotes()
    assert rd.stats["redis_calls"] == calls
    errs = [x for x in ui_lines(caplog) if x[1] == "ERR-SYS-001"]
    assert len(errs) == 1                                        # log tối đa 1 lần/phút
    t[0] = 11.0
    assert rd.available and rd.quotes() is None                  # thử lại sau 10s
    assert rd.health()["redis"]["ok"] is False


def test_t4_page_fallback_apptest(cfg, tmp_path, monkeypatch):
    """Toàn trang qua Streamlit AppTest với Redis down: banner dự phòng, không exception."""
    from streamlit.testing.v1 import AppTest
    import pandas as pd
    monkeypatch.setenv("UI_REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setenv("UI_SQLITE_PATH", str(tmp_path / "signals.db"))
    monkeypatch.setattr(data, "_READER", None)
    import datasource.cache as cache
    monkeypatch.setattr(cache, "read_cache", lambda: pd.DataFrame({"Mã": ["FPT"], "Giá": [58.1]}))
    at = AppTest.from_string("from ui.realtime_page import show_realtime\nshow_realtime()", default_timeout=30).run()
    assert not at.exception, at.exception
    assert any("dự phòng" in w.value for w in at.warning)


def test_t1_page_live_apptest(cfg, r, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    r.set("quote:FPT", _quote("FPT", 58100))
    monkeypatch.setenv("UI_REDIS_URL", TEST_URL)
    monkeypatch.setenv("UI_SQLITE_PATH", str(tmp_path / "signals.db"))
    monkeypatch.setattr(data, "_READER", None)
    at = AppTest.from_string("from ui.realtime_page import show_realtime\nshow_realtime()", default_timeout=30).run()
    assert not at.exception, at.exception
    assert not any("dự phòng" in w.value for w in at.warning)
    assert any("Cập nhật lúc" in c.value for c in at.caption)
    assert len(at.dataframe) == 1
