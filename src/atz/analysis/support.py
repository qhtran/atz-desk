"""Đáy 6 tháng và đường cổ giữa các lần chạm."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from config import MIN_BARS, SUPPORT_BAND, SUPPORT_DAYS


def support_scan(bars: pd.DataFrame) -> dict[str, object]:
    """Đáy 6 tháng, số lần chạm vùng 1,5% rồi bật lên, và đáy trung tâm giữa các lần chạm."""
    work = bars.copy()
    for column in ("high", "low", "close"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    cutoff = date.today() - timedelta(days=SUPPORT_DAYS)
    window = work.loc[work["_day"] >= cutoff].reset_index(drop=True)
    if len(window) < MIN_BARS:
        window = work.reset_index(drop=True)
    if window["low"].dropna().empty or len(window) < 2:
        raise ValueError("chưa đủ phiên để quét đáy")
    support = float(window["low"].min())
    if support <= 0:
        raise ValueError("đáy không hợp lệ")
    zone_top = support * (1 + SUPPORT_BAND)
    flags = (window["low"].fillna(zone_top * 10) <= zone_top).fillna(False).to_numpy()
    closes = window["close"].fillna(0).to_numpy(dtype=float)
    highs = window["high"].fillna(0).to_numpy(dtype=float)
    count = len(window)
    tests = 0
    touch_at = [index for index, flag in enumerate(flags) if flag]
    cursor = 0
    while cursor < count:
        if not flags[cursor]:
            cursor += 1
            continue
        while cursor < count and flags[cursor]:
            cursor += 1
        bounced = cursor < count and bool((closes[cursor:] > zone_top).any())
        if bounced or cursor >= count:
            tests += 1
    if len(touch_at) >= 2:
        between = [highs[index] for index in range(touch_at[0], touch_at[-1]) if not flags[index] and highs[index] > 0]
        neckline = float(max(between)) if between else float(max(highs[touch_at[0] : touch_at[-1] + 1]))
    else:
        low_at = int(window["low"].idxmin())
        segment = [highs[index] for index in range(low_at + 1, count) if highs[index] > 0]
        neckline = float(max(segment)) if segment else float(highs[low_at])
    price = float(closes[-1])
    previous = float(closes[-2])
    return {
        "support": support,
        "zone_top": zone_top,
        "tests": tests,
        "in_zone": price <= zone_top,
        "neckline": neckline,
        "crossed": previous <= neckline < price,
        "price": price,
    }
