"""Lớp dữ liệu UI realtime (không import Streamlit).

- Redis: quote:{symbol} (MGET), pos:live:{uid}, inapp:{uid}, health keys. Cache trong process ~1.5s
  dùng chung mọi session -> 100 user vẫn chỉ ~1 MGET / 1.5s.
- Redis lỗi: ERR-SYS-001 (log tối đa 1 lần/phút), bỏ qua Redis trong redis_retry_after_seconds, trả None
  để UI chuyển dự phòng.
- SQLite: positions (tái dùng position_monitor.store), users (cài đặt thông báo). Mọi thao tác vị thế
  đều lọc theo user_id đăng nhập (ERR-UI-002 nếu không thuộc user).
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from datetime import datetime, time as dtime
from pathlib import Path

import redis

from position_monitor import store as pos_store
from ui_realtime import config as ui_config
from ui_realtime.log import (ERR_SYS_REDIS, ERR_SYS_SQLITE, ERR_UI_FORBIDDEN, ERR_UI_INPUT, ERR_UI_SETTINGS, TZ, log)


class UserError(ValueError):
    """Lỗi nhập liệu hiển thị cho user; mang error_code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- giờ giao dịch
def _t(v: str) -> dtime:
    h, m = v.split(":")
    return dtime(int(h), int(m))


def in_trading(cfg: dict, now: datetime | None = None) -> bool:
    now = (now or datetime.now(TZ)).astimezone(TZ)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return any(_t(a) <= t <= _t(b) for a, b in cfg["ui_realtime"]["trading_sessions"])


def refresh_seconds(cfg: dict, now: datetime | None = None) -> float | None:
    u = cfg["ui_realtime"]
    sec = u["refresh_seconds_trading"] if in_trading(cfg, now) else u["refresh_seconds_off"]
    return float(sec) if sec else None


# ---------------------------------------------------------------- Redis reader
class RedisReader:
    def __init__(self, cfg: dict, client=None, clock=time.monotonic):
        self.cfg, self.u = cfg, cfg["ui_realtime"]
        self.clock = clock
        self.r = client or redis.Redis.from_url(cfg["redis"]["url"], decode_responses=True,
                                                socket_timeout=self.u["redis_timeout_seconds"],
                                                socket_connect_timeout=self.u["redis_timeout_seconds"])
        self._cache: dict = {}
        self._lock = threading.Lock()
        self._down_until = 0.0
        self._last_err_log = -1e18
        self.last_error: str | None = None
        self.stats = {"redis_calls": 0, "cache_hits": 0, "errors": 0}

    @property
    def available(self) -> bool:
        return self.clock() >= self._down_until

    def _fail(self, what: str, e: Exception) -> None:
        self.stats["errors"] += 1
        self.last_error = f"{type(e).__name__}: {e}"
        self._down_until = self.clock() + float(self.u["redis_retry_after_seconds"])
        if self.clock() - self._last_err_log >= float(self.u["error_log_every_seconds"]):
            self._last_err_log = self.clock()
            log("REDIS", f"redis read failed ({what}): {self.last_error}; fallback for {self.u['redis_retry_after_seconds']}s",
                logging.ERROR, error_code=ERR_SYS_REDIS)

    def _cached(self, key, ttl: float, fn):
        now = self.clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < ttl:
                self.stats["cache_hits"] += 1
                return hit[1]
        if not self.available:
            return None
        try:
            self.stats["redis_calls"] += 1
            val = fn()
        except (redis.exceptions.RedisError, OSError) as e:
            self._fail(str(key), e)
            return None
        self._down_until = 0.0
        with self._lock:
            self._cache[key] = (self.clock(), val)
        return val

    def symbols(self) -> list[str] | None:
        prefix = self.u["quote_key"].split("{")[0]
        return self._cached(("symbols",), float(self.u["symbols_cache_seconds"]),
                            lambda: sorted(k[len(prefix):] for k in self.r.scan_iter(match=prefix + "*", count=500)))

    def quotes(self) -> list[dict] | None:
        syms = self.symbols()
        if syms is None:
            return None
        if not syms:
            return []
        keys = [self.u["quote_key"].format(symbol=s) for s in syms]

        def fetch():
            out = []
            for raw in self.r.mget(keys):
                if raw:
                    try:
                        out.append(json.loads(raw))
                    except ValueError:
                        continue
            return out
        return self._cached(("quotes", tuple(keys)), float(self.u["cache_ttl_seconds"]), fetch)

    def live_positions(self, user_id: int) -> dict | None:
        key = self.u["live_key"].format(user_id=int(user_id))
        raw = self._cached(("live", key), float(self.u["cache_ttl_seconds"]), lambda: self.r.hgetall(key))
        if raw is None:
            return None
        out = {}
        for pid, val in raw.items():
            try:
                out[int(pid)] = json.loads(val)
            except ValueError:
                continue
        return out

    def inapp(self, user_id: int) -> list[dict] | None:
        key = self.u["inapp_key"].format(user_id=int(user_id))
        n = int(self.u["inapp_show"])
        raw = self._cached(("inapp", key), float(self.u["cache_ttl_seconds"]), lambda: self.r.lrange(key, 0, n - 1))
        if raw is None:
            return None
        out = []
        for val in raw:
            try:
                d = json.loads(val)
            except ValueError:
                continue
            if str(d.get("user_id", user_id)) == str(user_id):   # cách ly: chỉ tin của chính user
                out.append(d)
        return out

    def seen(self, user_id: int) -> str:
        if not self.available:
            return ""
        try:
            return self.r.get(self.u["inapp_seen_key"].format(user_id=int(user_id))) or ""
        except (redis.exceptions.RedisError, OSError) as e:
            self._fail("seen", e)
            return ""

    def mark_seen(self, user_id: int, ts: str) -> bool:
        try:
            self.r.set(self.u["inapp_seen_key"].format(user_id=int(user_id)), ts)
            return True
        except (redis.exceptions.RedisError, OSError) as e:
            self._fail("mark_seen", e)
            return False

    def health(self) -> dict:
        """Mini-panel admin: redis ping+memory + heartbeat từng service (tuổi, ok)."""
        h = self.u["health"]
        out = {}
        try:
            t0 = time.monotonic()
            self.r.ping()
            mem = self.r.info("memory").get("used_memory_human")
            out["redis"] = {"ok": True, "detail": f"ping {int((time.monotonic()-t0)*1000)}ms, mem {mem}"}
            raws = self.r.mget(list(h["keys"].values()))
        except (redis.exceptions.RedisError, OSError) as e:
            self._fail("health", e)
            out["redis"] = {"ok": False, "detail": f"{ERR_SYS_REDIS} {type(e).__name__}"}
            for name in h["keys"]:
                out[name] = {"ok": False, "detail": "redis down"}
            return out
        now = time.time()
        for (name, _), raw in zip(h["keys"].items(), raws):
            if not raw:
                out[name] = {"ok": False, "detail": "heartbeat missing"}
                continue
            try:
                beat = json.loads(raw)
                age = now - float(beat.get("epoch", 0))
            except (ValueError, TypeError):
                out[name] = {"ok": False, "detail": "heartbeat hỏng"}
                continue
            extra = {"ingestion": lambda b: f"mode {b.get('mode')}, rpm {b.get('current_rpm')}, {b.get('breakers')}",
                     "filter": lambda b: f"{b.get('signals_per_minute')} signal/phút, disabled {b.get('disabled_filters')}",
                     "alert": lambda b: ", ".join(f"{k}:{v.get('circuit')}" for k, v in (b.get("channels") or {}).items()),
                     "position": lambda b: f"{b.get('open_positions')} vị thế mở, stale {b.get('stale_positions')}",
                     "index": lambda b: f"{b.get('fresh')}/{b.get('symbols')} mã mới, nguồn "
                                        + ", ".join(f"{k}:{v.get('circuit') if v.get('enabled') else 'off'}"
                                                    for k, v in (b.get("providers") or {}).items())}
            ok = age <= float(h["max_age_seconds"]) and not (name == "ingestion" and beat.get("mode") == "degraded") \
                and not (name == "index" and beat.get("fresh", 0) < beat.get("symbols", 0))
            out[name] = {"ok": ok, "detail": f"heartbeat {age:.0f}s; " + extra.get(name, lambda b: "")(beat)}
        return out


def _vnd_int(value: object) -> int | None:
    """Trần/Sàn/giá VND → int (bỏ .000000)."""
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def quote_status_label(*, stale: bool, trading: bool) -> str:
    """Ngoài phiên không hiện ``live`` (DoD T-152)."""
    if stale:
        return "⚠️ cũ"
    if not trading:
        return "closed"
    return "live"


def quote_rows(
    quotes: list[dict],
    stale_seconds: float,
    now: datetime | None = None,
    *,
    trading: bool | None = None,
) -> list[dict]:
    """Quote -> dòng bảng giá (VND). stale nếu ingestion gắn cờ hoặc tuổi > stale_seconds."""
    now = (now or datetime.now(TZ)).astimezone(TZ)
    if trading is None:
        try:
            trading = in_trading(ui_config.load(), now)
        except Exception:  # noqa: BLE001
            trading = True
    rows = []
    for q in quotes:
        try:
            ts = datetime.fromisoformat(str(q.get("timestamp")))
            age = (now - ts).total_seconds()
        except ValueError:
            ts, age = None, None
        flagged = str(q.get("stale")).lower() in ("true", "1")
        stale = flagged or age is None or age > stale_seconds
        rows.append({"Mã": q.get("symbol"), "Giá": q.get("price"), "+/-": q.get("change"), "%": q.get("change_pct"),
                     "Mở": q.get("open"), "Cao": q.get("high"), "Thấp": q.get("low"), "TC": q.get("ref_price"),
                     "Trần": _vnd_int(q.get("ceiling_price")), "Sàn giá": _vnd_int(q.get("floor_price")),
                     "Sàn": str(q.get("exchange") or ""),
                     "Nguồn": str(q.get("source") or "").upper(), "Lúc": ts.astimezone(TZ).strftime("%H:%M:%S") if ts else "?",
                     "Trạng thái": quote_status_label(stale=stale, trading=bool(trading)),
                     "_stale": stale, "_ts": ts})
    rows.sort(key=lambda r: r["Mã"] or "")
    return rows


# ---------------------------------------------------------------- SQLite
_MIGRATED: set[str] = set()
_MIGRATE_LOCK = threading.Lock()


def open_db(cfg: dict) -> sqlite3.Connection:
    """Dùng chung migration của Module 4 (positions) + Module 3 (users.telegram_chat_id). Chỉ additive.

    Migration chạy 1 lần/process/đường dẫn DB; các lần sau chỉ mở kết nối. Caller phải close()
    (dùng contextlib.closing; `with conn:` của sqlite3 chỉ commit, không đóng)."""
    path = str(cfg["sqlite"]["path"])
    with _MIGRATE_LOCK:
        if path not in _MIGRATED:
            from alert_dispatcher.store import migrate_alert
            conn = pos_store.open_db(path)
            migrate_alert(conn)
            _MIGRATED.add(path)
            return conn
    conn = pos_store.connect(Path(path))
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def user_id_for(conn, username: str) -> int:
    from storage.repository import ensure_user
    return ensure_user(conn, username)


def _num(v, name: str, required: bool) -> float | None:
    if v in (None, "", 0, 0.0) and not required:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise UserError(ERR_UI_INPUT, f"{name} không phải số") from None
    return x


def add_position(conn, user_id: int, symbol: str, qty, entry, sl=None, tp=None, note: str | None = None,
                 unit: str = "vnd") -> int:
    """Cùng validation với position_monitor.cli add (store.add). unit 'k' = nghìn đồng."""
    k = 1000.0 if unit == "k" else 1.0
    q, e = _num(qty, "Khối lượng", True), _num(entry, "Giá vốn", True)
    s, t = _num(sl, "Cắt lỗ", False), _num(tp, "Chốt lời", False)
    symbol = (symbol or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", symbol):
        raise UserError(ERR_UI_INPUT, "Mã không hợp lệ")
    try:
        pid = pos_store.add(conn, int(user_id), symbol, q, e * k, None if s is None else s * k,
                            None if t is None else t * k, (note or "").strip() or None)
    except ValueError as err:
        log("POS-ADD", f"rejected: {err}", error_code=ERR_UI_INPUT, symbol=symbol, user_id=user_id)
        raise UserError(ERR_UI_INPUT, str(err)) from None
    except sqlite3.OperationalError as err:
        log("POS-ADD", f"sqlite: {err}", logging.ERROR, error_code=ERR_SYS_SQLITE, symbol=symbol, user_id=user_id)
        raise UserError(ERR_SYS_SQLITE, "Cơ sở dữ liệu đang bận, thử lại") from None
    log("POS-ADD", f"position={pid} qty={q} entry={e*k} sl={s} tp={t}", symbol=symbol, user_id=user_id, position_id=pid)
    return pid


def list_positions(conn, user_id: int, include_closed: bool = False) -> list[dict]:
    rows = pos_store.list_all(conn, int(user_id))
    return rows if include_closed else [r for r in rows if r["status"] == "open"]


def _owned(conn, user_id: int, position_id: int) -> dict:
    row = conn.execute("SELECT * FROM positions WHERE id = ? AND user_id = ?", (int(position_id), int(user_id))).fetchone()
    if row is None:
        log("POS-OWN", f"position={position_id} not owned / not found", error_code=ERR_UI_FORBIDDEN, user_id=user_id,
            position_id=position_id)
        raise UserError(ERR_UI_FORBIDDEN, "Không tìm thấy vị thế của bạn")
    return dict(row)


def update_levels(conn, user_id: int, position_id: int, sl=None, tp=None, unit: str = "vnd") -> None:
    """Đổi SL/TP (để trống = giữ nguyên). Validation LONG như khi thêm. Đổi mức -> bật lại cảnh báo mức đó."""
    p = _owned(conn, user_id, position_id)
    if p["status"] != "open":
        raise UserError(ERR_UI_INPUT, "Vị thế đã đóng")
    k = 1000.0 if unit == "k" else 1.0
    s, t = _num(sl, "Cắt lỗ", False), _num(tp, "Chốt lời", False)
    s, t = (None if s is None else s * k), (None if t is None else t * k)
    if s is None and t is None:
        raise UserError(ERR_UI_INPUT, "Chưa nhập mức mới")
    if s is not None and not 0 < s < p["entry_price"]:
        raise UserError(ERR_UI_INPUT, "stop_loss phải < entry_price (vị thế LONG)")
    if t is not None and t <= p["entry_price"]:
        raise UserError(ERR_UI_INPUT, "take_profit phải > entry_price (vị thế LONG)")
    pos_store.update_levels(conn, p["id"], s, t)
    log("POS-SET", f"position={p['id']} sl={s} tp={t}", symbol=p["symbol"], user_id=user_id, position_id=p["id"])


def close_position(conn, user_id: int, position_id: int) -> bool:
    p = _owned(conn, user_id, position_id)
    ok = pos_store.close(conn, p["id"])
    log("POS-CLOSE", f"position={p['id']} closed={ok}", symbol=p["symbol"], user_id=user_id, position_id=p["id"])
    return ok


# ---------------------------------------------------------------- cài đặt thông báo
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def get_settings(conn, user_id: int) -> dict:
    from alert_dispatcher.store import get_user
    u = get_user(conn, str(int(user_id))) or {}
    s = u.get("cai_dat_chung") or {}
    return {"telegram_chat_id": u.get("telegram_chat_id") or "", "telegram_bat": bool(s.get("telegram_bat", True)),
            "email": u.get("email_nhan_thong_bao") or "", "email_bat": bool(s.get("email_bat", False)),
            "quiet_hours": s.get("quiet_hours") or None}


def save_settings(conn, user_id: int, telegram_chat_id: str, telegram_bat: bool, email: str, email_bat: bool,
                  quiet_start: str | None, quiet_end: str | None) -> None:
    chat = (telegram_chat_id or "").strip()
    if chat and not re.fullmatch(r"-?\d{5,20}", chat):
        raise UserError(ERR_UI_SETTINGS, "Telegram chat_id phải là số (vd 8505117958 hoặc -100…)")
    mail = (email or "").strip()
    if mail and not _EMAIL.match(mail):
        raise UserError(ERR_UI_SETTINGS, "Email không hợp lệ")
    if email_bat and not mail:
        raise UserError(ERR_UI_SETTINGS, "Bật email cần nhập địa chỉ email")
    qs, qe = (quiet_start or "").strip(), (quiet_end or "").strip()
    if bool(qs) != bool(qe) or (qs and not (_HHMM.match(qs) and _HHMM.match(qe))) or (qs and qs == qe):
        raise UserError(ERR_UI_SETTINGS, "Giờ yên lặng cần cả bắt đầu và kết thúc dạng HH:MM, khác nhau")
    row = conn.execute("SELECT cai_dat_chung FROM users WHERE id = ?", (int(user_id),)).fetchone()
    if row is None:
        raise UserError(ERR_UI_SETTINGS, "Không tìm thấy user")
    try:
        s = json.loads(row["cai_dat_chung"] or "{}")
    except ValueError:
        s = {}
    s["telegram_bat"], s["email_bat"] = bool(telegram_bat), bool(email_bat)
    if qs:
        s["quiet_hours"] = {"start": qs, "end": qe}
    else:
        s.pop("quiet_hours", None)
    try:
        conn.execute("UPDATE users SET telegram_chat_id = ?, email_nhan_thong_bao = ?, cai_dat_chung = ? WHERE id = ?",
                     (chat or None, mail or None, json.dumps(s, ensure_ascii=False), int(user_id)))
        conn.commit()
    except sqlite3.OperationalError as err:
        log("SETTINGS", f"sqlite: {err}", logging.ERROR, error_code=ERR_SYS_SQLITE, user_id=user_id)
        raise UserError(ERR_SYS_SQLITE, "Cơ sở dữ liệu đang bận, thử lại") from None
    log("SETTINGS", f"saved telegram={'set' if chat else 'none'} telegram_bat={telegram_bat} email={'set' if mail else 'none'} "
        f"email_bat={email_bat} quiet={qs or '-'}-{qe or '-'}", user_id=user_id)


# ---------------------------------------------------------------- singleton theo process
_READER: RedisReader | None = None
_READER_LOCK = threading.Lock()


def reader() -> RedisReader:
    global _READER
    with _READER_LOCK:
        if _READER is None:
            _READER = RedisReader(ui_config.load())
        return _READER
