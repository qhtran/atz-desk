"""Đồng hồ phiên HOSE theo giờ Hà Nội."""

from __future__ import annotations

from datetime import datetime

from config import HN_ZONE, SESSION_AFTERNOON, SESSION_MORNING


def market_session(moment: datetime | None = None) -> tuple[str, str]:
    """Sáng 9:00–11:30 và chiều 13:00–14:45 theo giờ Hà Nội. Cuối tuần là ngoài phiên."""
    current = moment or datetime.now(HN_ZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=HN_ZONE)
    else:
        current = current.astimezone(HN_ZONE)
    clock = current.strftime("%H:%M %d/%m/%Y")
    if current.weekday() >= 5:
        return "Ngoài phiên", clock
    minute = current.hour * 60 + current.minute
    morning = SESSION_MORNING[0] <= minute <= SESSION_MORNING[1]
    afternoon = SESSION_AFTERNOON[0] <= minute <= SESSION_AFTERNOON[1]
    return ("Trong phiên" if morning or afternoon else "Ngoài phiên"), clock
