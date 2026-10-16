"""Preference Resolver: users.telegram_chat_id, users.email_nhan_thong_bao, cai_dat_chung.

cai_dat_chung keys dùng: telegram_bat (mặc định True nếu có chat_id), email_bat, loai_nhan ["mua","ban"], quiet_hours {start,end}.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime


@dataclass
class Prefs:
    found: bool
    telegram_chat_id: str | None = None
    email: str | None = None
    wants: bool = True
    quiet_hours: dict | None = None
    channels: list[str] = field(default_factory=list)


def resolve(user: dict | None, sig: dict, default_quiet=None) -> Prefs:
    if user is None:
        return Prefs(found=False, quiet_hours=default_quiet)
    s = user.get("cai_dat_chung") or {}
    allowed = s.get("loai_nhan")
    sig_type = "mua" if sig["direction"] == "BUY" else "ban"
    p = Prefs(found=True, wants=allowed is None or sig_type in allowed,
              quiet_hours=s.get("quiet_hours", default_quiet))
    if user.get("telegram_chat_id") and s.get("telegram_bat", True):
        p.telegram_chat_id = str(user["telegram_chat_id"])
        p.channels.append("telegram")
    if user.get("email_nhan_thong_bao") and s.get("email_bat"):
        p.email = user["email_nhan_thong_bao"]
        p.channels.append("email")
    return p


def _t(v: str) -> dtime:
    h, m = v.split(":")
    return dtime(int(h), int(m))


def in_quiet(qh: dict | None, now: datetime) -> bool:
    if not qh or not qh.get("start") or not qh.get("end"):
        return False
    a, b, t = _t(qh["start"]), _t(qh["end"]), now.time()
    return a <= t < b if a <= b else (t >= a or t < b)
