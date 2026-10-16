"""Module 3 - Alert Dispatcher. Chạy trong container (cần Redis thật):

docker compose run --rm --no-deps -v ./tests:/app/tests -v ./pytest.ini:/app/pytest.ini alert-dispatcher pytest -q -s tests/test_alert_dispatcher.py
T1-T3 dùng Redis DB 14 (flush) + SQLite tạm, adapter giả. Integration (ALERT_IT=1): Telegram thật tới channel broadcast.
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

from alert_dispatcher import config, store
from alert_dispatcher.adapters import ChannelError
from alert_dispatcher.dispatcher import Dispatcher
from alert_dispatcher.health import check
from alert_dispatcher.log import TZ

LABEL = re.compile(r"^\[DBG-\d{8}-\d{4}-ALERT-([A-Z]+)\]( (ERR-[A-Z]+-\d{3}))? (\{.*\})$")
TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://redis:6379/14")


def entries(caplog):
    out = []
    for rec in caplog.records:
        if rec.name != "alert_dispatcher":
            continue
        m = LABEL.match(rec.getMessage())
        assert m, f"log sai format: {rec.getMessage()}"
        d = json.loads(m.group(4))
        for k in ("debug_label", "error_code", "module", "symbol", "user_id", "latency_ms", "message"):
            assert k in d
        assert d["module"] == "ALERT" and d["error_code"] == m.group(3)
        out.append((m.group(1), d, rec.getMessage()))
    return out


def codes(caplog):
    return [d["error_code"] for _a, d, _l in entries(caplog) if d["error_code"]]


@pytest.fixture(autouse=True)
def _logs(caplog):
    caplog.set_level(logging.INFO, logger="alert_dispatcher")


@pytest.fixture
def r():
    c = redis.Redis.from_url(TEST_URL, decode_responses=True)
    c.flushdb()
    yield c
    c.flushdb()


class FakeTG:
    def __init__(self, fail=False):
        self.fail, self.sent = fail, []

    def send(self, chat_id, text):
        if self.fail:
            raise ChannelError("HTTP 502")
        self.sent.append((str(chat_id), text))
        return "1"


class FakeMail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, text):
        self.sent.append(to)
        return "smtp"


def cfg_for(tmp_path, email=False, broadcast=("-100999",), quiet=None):
    cfg = copy.deepcopy(config.load())
    cfg["redis"]["url"] = TEST_URL
    cfg["sqlite"]["path"] = str(tmp_path / "signals.db")
    ch = cfg["alert_dispatcher"]["channels"]
    ch["telegram"]["broadcast_chat_ids"] = list(broadcast)
    ch["telegram"]["retries"] = 0
    ch["email"]["enabled"] = email
    cfg["alert_dispatcher"]["quiet_hours"]["default"] = quiet
    return cfg


def make_user(db, chat="555", email=None, settings=None):
    db.execute("INSERT INTO users (username, email_nhan_thong_bao, cai_dat_chung, created_at, telegram_chat_id) VALUES (?,?,?,?,?)",
               ("u", email, json.dumps(settings or {}), "now", chat))
    db.commit()
    return "1"


def sig(i=0, user="1", symbol="VNM", direction="BUY"):
    return {"signal_id": f"sig_t{i}_{time.time_ns()}", "user_id": user, "symbol": symbol,
            "timestamp": datetime.now(TZ).isoformat(timespec="seconds"), "filter_name": f"rsi{i}",
            "direction": direction, "price": 62500.0, "reason": "test", "confidence": 0.8}


def build(tmp_path, r, tg=None, mail=None, **kw):
    cfg = cfg_for(tmp_path, email=mail is not None, **kw)
    db = store.open_db(cfg["sqlite"]["path"])
    ad = {"telegram": tg or FakeTG()}
    if mail is not None:
        ad["email"] = mail
    return Dispatcher(cfg, r=r, db=db, adapters=ad), db


def test_t1_route_telegram_history_delivery_inapp(tmp_path, r, caplog):
    d, db = build(tmp_path, r)
    uid = make_user(db)
    s = sig()
    r.xadd("stream:signals", {k: str(v) for k, v in s.items()})   # đúng format publisher Module 2 (sau khi group tạo)
    assert d.step() == 1
    tg = d.adapters["telegram"]
    assert sorted(c for c, _ in tg.sent) == ["-100999", "555"]
    assert "VNM" in tg.sent[0][1] and "MUA" in tg.sent[0][1]
    h = db.execute("SELECT * FROM signal_history").fetchall()
    assert len(h) == 1 and h[0]["notified"] == 1 and h[0]["signal_type"] == "mua"
    rows = db.execute("SELECT channel, status FROM alert_deliveries ORDER BY id").fetchall()
    assert sorted((x[0], x[1]) for x in rows) == [("inapp", "sent"), ("telegram", "sent"), ("telegram", "sent")]
    assert r.llen(f"inapp:{uid}") == 1
    assert d.handle(s).get("dedup") is True                  # cùng signal_id -> bỏ
    beat = d.write_health()
    assert beat["channels"]["telegram"]["success_rate"] == 1.0 and beat["channels"]["email"]["circuit"] == "disabled"
    assert check(d.cfg, r)[0] is True
    assert codes(caplog) == []
    print("\n".join(l for *_x, l in entries(caplog)[:4]))


def test_t2_telegram_fail_circuit_fallback_email(tmp_path, r, caplog):
    mail = FakeMail()
    d, db = build(tmp_path, r, tg=FakeTG(fail=True), mail=mail, broadcast=())
    make_user(db, email="a@b.vn", settings={"email_bat": True})
    for i in range(7):
        d.handle(sig(i))
    c = codes(caplog)
    assert c.count("ERR-ALERT-001") == 5                     # 5 lỗi -> circuit open
    assert "ERR-ALERT-003" in c                              # các lần sau: circuit open, không gọi telegram
    assert len(mail.sent) == 7                               # fallback email mỗi lần
    assert d.circuits["telegram"].state == "open"
    assert d.health()["channels"]["telegram"]["success_rate"] == 0.0
    print("\n".join(l for *_x, l in entries(caplog) if "ERR-ALERT-00" in l)[:1200])


class FakeResp:
    def __init__(self, body):
        self.b = json.dumps(body).encode()

    def read(self, *a):
        return self.b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_t2c_brevo_api_adapter_mock(tmp_path, r, caplog):
    import io
    import urllib.error
    from alert_dispatcher.adapters import EmailAdapter
    calls = []

    def ok(req, timeout):
        calls.append(req)
        return FakeResp({"messageId": "<abc@smtp-relay.mailin.fr>"})
    a = EmailAdapter(5, 0, api_key="k-test", opener=ok)
    d, db = build(tmp_path, r, tg=FakeTG(fail=True), mail=a, broadcast=())
    make_user(db, chat=None, email="a@b.vn", settings={"email_bat": True})
    assert d.handle(sig(1))["user"] == ["sent"]
    req = calls[0]
    body = json.loads(req.data)
    assert req.full_url == "https://api.brevo.com/v3/smtp/email" and req.get_header("Api-key") == "k-test"
    assert body["to"] == [{"email": "a@b.vn"}] and body["sender"]["email"] == "mail@atz.vn"
    row = db.execute("SELECT target, provider_message_id FROM alert_deliveries WHERE channel='email'").fetchone()
    assert row[0] == "a***@b.vn" and row[1] == "<abc@smtp-relay.mailin.fr>"

    def bad(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "x", {}, io.BytesIO(b'{"message":"Key not found"}'))
    d.adapters["email"].opener = bad
    for i in range(5):
        d.handle(sig(10 + i))
    assert codes(caplog).count("ERR-ALERT-002") == 5 and d.circuits["email"].state == "open"
    assert "k-test" not in caplog.text


def test_t2b_email_disabled_no_error_spam(tmp_path, r, caplog):
    d, db = build(tmp_path, r, broadcast=())   # mail=None -> email enabled=false
    make_user(db, chat=None, email="a@b.vn", settings={"email_bat": True})
    for i in range(5):
        d.handle(sig(i))
    assert "email" not in d.circuits
    assert codes(caplog) == ["ERR-ALERT-005"]               # chỉ 1 cảnh báo pref/giờ, không ERR-ALERT-002/003
    assert r.llen("inapp:1") == 5


def test_t3_rate_limit_quiet_pref(tmp_path, r, caplog):
    d, db = build(tmp_path, r, broadcast=())
    make_user(db)
    res = [d.handle(sig(i))["user"][0] for i in range(12)]
    assert res.count("sent") == 10 and res[10:] == ["rate", "rate"]
    assert codes(caplog).count("ERR-ALERT-004") == 2
    # 30/hour: dịch đồng hồ qua 5 phút nhiều lần
    t = [time.time()]
    d.limiter.clock = d.clock = lambda: t[0]
    sent = 10
    for k in range(6):
        t[0] += 301
        sent += sum(d.handle(sig(100 + k * 20 + i))["user"][0] == "sent" for i in range(10))
    assert sent == 30
    # quiet hours luôn đúng + user không có trong DB
    db.execute("UPDATE users SET cai_dat_chung = ?", (json.dumps({"quiet_hours": {"start": "00:00", "end": "23:59"}}),))
    db.commit()
    t[0] += 7200
    assert d.handle(sig(999))["user"] == ["quiet"]
    assert d.handle(sig(998, user="default"))["user"] == ["nopref"]
    assert "ERR-ALERT-005" in codes(caplog)


@pytest.mark.skipif(os.environ.get("ALERT_IT") != "1", reason="ALERT_IT=1 để gửi Telegram thật")
def test_integration_real_telegram_broadcast(tmp_path, r, caplog):
    real = config.load()
    cfg = cfg_for(tmp_path, broadcast=real["alert_dispatcher"]["channels"]["telegram"]["broadcast_chat_ids"])
    cfg["alert_dispatcher"]["channels"]["telegram"]["retries"] = 2
    d = Dispatcher(cfg, r=r, db=store.open_db(cfg["sqlite"]["path"]))
    s = sig(symbol="TEST")
    s["reason"] = f"[DBG-{datetime.now(TZ):%Y%m%d-%H%M}-ALERT-IT] integration test, bỏ qua"
    r.xadd("stream:signals", {k: str(v) for k, v in s.items()})
    assert d.step() == 1
    assert d.stats["telegram"]["sent"] == 1 and d.stats["telegram"]["failed"] == 0
    assert codes(caplog) == ["ERR-ALERT-005"]               # user "1" không có trong DB tạm -> chỉ broadcast
    print("\n".join(l for *_x, l in entries(caplog)))
