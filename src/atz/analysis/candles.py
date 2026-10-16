"""Mẫu nến của một phiên. Ngưỡng thân và bóng nằm trong config.CANDLE."""

from __future__ import annotations

import pandas as pd

from config import CANDLE


def _body_parts(row: pd.Series) -> tuple[float, float, float, float]:
    open_ = float(row["open"])
    close = float(row["close"])
    high = float(row["high"])
    low = float(row["low"])
    span = high - low
    body = abs(close - open_)
    upper = high - max(open_, close)
    lower = min(open_, close) - low
    return span, body, upper, lower


def candle_pattern(bars: pd.DataFrame) -> str | None:
    """Mẫu hình của phiên cuối: Engulfing, Hammer, Shooting Star hoặc Doji."""
    work = bars[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").fillna(0)
    if len(work) < 2:
        return None
    last = work.iloc[-1]
    previous = work.iloc[-2]
    span, body, upper, lower = _body_parts(last)
    if span <= 0:
        return None
    prev_open = float(previous["open"])
    prev_close = float(previous["close"])
    open_ = float(last["open"])
    close = float(last["close"])
    bullish = close > open_ and prev_close < prev_open and open_ <= prev_close and close >= prev_open
    bearish = close < open_ and prev_close > prev_open and open_ >= prev_close and close <= prev_open
    shadow = CANDLE["SHADOW_BODY"]
    if bullish and body > 0:
        return "Engulfing tăng"
    if bearish and body > 0:
        return "Engulfing giảm"
    if body > 0 and lower >= body * shadow and upper <= body and lower > upper:
        return "Hammer"
    if body > 0 and upper >= body * shadow and lower <= body and upper > lower:
        return "Shooting Star"
    if body <= span * CANDLE["DOJI_BODY_RATIO"]:
        return "Doji"
    return None


def explain_pattern(name: str) -> str:
    notes = {
        "Doji": (
            "Theo John J. Murphy và Steve Nison, Doji thể hiện sự lưỡng lự tuyệt đối của thị trường, "
            "cung cầu cân bằng, cần đợi nến ngày tiếp theo để xác nhận xu hướng."
        ),
        "Hammer": (
            "Theo Steve Nison, Hammer là nến có bóng dưới dài và thân nhỏ phía trên: "
            "phe bán đã bị đẩy lùi trong phiên. Tín hiệu tăng cần nến sau xác nhận."
        ),
        "Shooting Star": (
            "Theo Steve Nison, Shooting Star là nến có bóng trên dài và thân nhỏ phía dưới: "
            "giá bị từ chối ở vùng cao. Tín hiệu giảm cần nến sau xác nhận."
        ),
        "Engulfing tăng": (
            "Theo John J. Murphy, nến nhấn chìm tăng là thân xanh phủ kín thân đỏ phía trước, "
            "phe mua giành lại quyền kiểm soát."
        ),
        "Engulfing giảm": (
            "Theo John J. Murphy, nến nhấn chìm giảm là thân đỏ phủ kín thân xanh phía trước, "
            "phe bán giành lại quyền kiểm soát."
        ),
    }
    return notes[name]


BULLISH_REVERSAL = ("Engulfing tăng", "Hammer")


def reversal_at_support(bars: pd.DataFrame) -> dict[str, object]:
    """Nến đảo chiều tăng ở phiên cuối và có chạm vùng hỗ trợ (F1 mục 7, hàng 1).

    Hỗ trợ lấy từ analysis.support.support_scan (đáy 6 tháng + dải SUPPORT_BAND).
    Chạm = low thấp nhất của 2 phiên cuối nằm trong vùng. Ném ValueError khi thiếu dữ liệu.
    """
    from analysis.support import support_scan

    pattern = candle_pattern(bars)
    scan = support_scan(bars)
    lows = pd.to_numeric(bars["low"], errors="coerce").tail(2)
    if lows.isna().all():
        raise ValueError("thiếu giá thấp nhất 2 phiên cuối")
    touched = bool(float(lows.min()) <= float(scan["zone_top"]))
    return {
        "pattern": pattern,
        "bullish": pattern in BULLISH_REVERSAL,
        "at_support": touched,
        "support": round(float(scan["support"]), 4),
        "zone_top": round(float(scan["zone_top"]), 4),
        "support_tests": int(scan["tests"]),
    }
