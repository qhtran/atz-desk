"""Intraday position alerts (port of ui.sidebar_portfolio.position_alert for dev SPA)."""

from __future__ import annotations

ALERT_BANDS = (5.0, 8.0, 10.0)
NEAR_ZONE_PCT = 2.0


def position_alert(
    buy: float | None,
    current: float | None,
    support: float | None = None,
    resistance: float | None = None,
) -> str:
    """Ưu tiên hỗ trợ/kháng cự gần, rồi mốc ±5/8/10% so với giá mua."""
    if current is None:
        return "Chưa có giá"
    notes: list[str] = []
    if support is not None and support > 0:
        gap = (current - support) / support * 100
        if abs(gap) <= NEAR_ZONE_PCT:
            notes.append("Gần hỗ trợ")
        elif current < support:
            notes.append("Dưới hỗ trợ")
    if resistance is not None and resistance > 0:
        gap = (resistance - current) / resistance * 100
        if abs(gap) <= NEAR_ZONE_PCT:
            notes.append("Gần kháng cự")
        elif current > resistance:
            notes.append("Vượt kháng cự")
    if buy is not None and buy > 0:
        change = (current - buy) / buy * 100
        hit = None
        for band in ALERT_BANDS:
            if abs(change) + 0.05 >= band:
                hit = band
        if hit is not None:
            sign = "+" if change >= 0 else "−"
            notes.append(f"{sign}{hit:.0f}%")
    return " · ".join(notes) if notes else "—"
