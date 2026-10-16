"""Chuỗi spark 1 phút trong ngày + chia màu theo tham chiếu + rollover hợp đồng phái sinh."""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo


def _t(v: str) -> dtime:
    h, m = v.split(":")
    return dtime(int(h), int(m))


def local(epoch: float, tz: str) -> datetime:
    return datetime.fromtimestamp(epoch, ZoneInfo(tz))


def session_start_epoch(epoch: float, tz: str) -> int:
    d = local(epoch, tz)
    return int(d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def in_session(epoch: float, tz: str, sessions) -> bool:
    d = local(epoch, tz)
    return d.weekday() < 5 and any(_t(a) <= d.time() <= _t(b) for a, b in sessions)


def seconds_to_next_session(epoch: float, tz: str, sessions) -> int:
    """TTL cho spark:* = tới giờ mở cửa phiên kế tiếp (ngày làm việc sau, giờ mở đầu tiên) + 1h dư."""
    d = local(epoch, tz)
    start = _t(sessions[0][0])
    nxt = (d + timedelta(days=1)).replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return max(60, int((nxt - d).total_seconds()) + 3600)


class Spark:
    """Điểm [epoch_phút, giá trị] của một phiên; điểm cùng phút bị ghi đè (giá cuối phút)."""

    def __init__(self, symbol: str, tz: str, max_points: int = 300):
        self.symbol, self.tz, self.max = symbol, tz, max_points
        self.day: int | None = None
        self.contract: str | None = None
        self.points: list[list[float]] = []

    def reset(self, day: int | None = None, contract: str | None = None) -> None:
        self.day, self.points = day, []
        if contract is not None:
            self.contract = contract

    def load(self, bars, contract: str | None = None) -> None:
        """Backfill: giữ phiên mới nhất có trong bars."""
        if not bars:
            return
        last_day = session_start_epoch(bars[-1][0], self.tz)
        self.reset(last_day, contract)
        for t, v in bars:
            if session_start_epoch(t, self.tz) == last_day:
                self.add(t, v)

    def roll_if_needed(self, contract: str | None) -> bool:
        """Đổi mã hợp đồng (đáo hạn) -> xoá chuỗi cũ. Trả True nếu đã reset."""
        if contract and self.contract and contract != self.contract:
            self.reset(None, contract)
            return True
        if contract:
            self.contract = contract
        return False

    def add(self, epoch: float, value: float) -> None:
        day = session_start_epoch(epoch, self.tz)
        if self.day is None or day > self.day:
            self.reset(day)
        elif day < self.day:
            return
        minute = int(epoch) // 60 * 60
        if self.points and self.points[-1][0] == minute:
            self.points[-1][1] = value
        elif not self.points or minute > self.points[-1][0]:
            self.points.append([minute, value])
            if len(self.points) > self.max:
                del self.points[: len(self.points) - self.max]

    def to_json(self) -> dict:
        return {"symbol": self.symbol, "day": self.day, "contract": self.contract, "points": self.points}


def split_by_ref(values: list[float], ref: float) -> list[tuple[str, list[int]]]:
    """Chia chuỗi thành đoạn 'up' (>= ref) / 'down' (< ref) liên tiếp (theo chỉ số điểm). Dùng cho test + mô tả."""
    out: list[tuple[str, list[int]]] = []
    for i, v in enumerate(values):
        side = "up" if v >= ref else "down"
        if out and out[-1][0] == side:
            out[-1][1].append(i)
        else:
            out.append((side, [i]))
    return out
