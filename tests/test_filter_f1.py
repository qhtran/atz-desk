"""F1 mục 7 hàng 1–3: nến đảo chiều tại hỗ trợ, RSI đáy vùng 30, MACD cắt lên + histogram cải thiện."""

from __future__ import annotations

import pandas as pd

from analysis.technical import macd, macd_improving, rsi, rsi_bottoms
from filters import candle, macd as macd_filter, rsi as rsi_filter
from tests.bars import frame

# Dao động quanh 100, giảm sâu (đáy RSI 1), hồi, giảm lần 2 (đáy RSI 2 vùng 30), rồi tăng mạnh.
_RSI_STEPS = [1, -1] * 10 + [-2] * 10 + [2] * 5 + [-1.5] * 6 + [2.5] * 6


def _rsi_closes() -> list[float]:
    closes, price = [], 100.0
    for step in _RSI_STEPS:
        price += step
        closes.append(price)
    return closes


def _ohlc(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [f"2026-01-{day:02d}" for day in range(1, len(rows) + 1)],
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [1000.0] * len(rows),
        }
    )


def _decline(start: float, count: int) -> list[tuple[float, float, float, float]]:
    rows = []
    for index in range(count):
        open_ = start - index
        close = open_ - 0.8
        rows.append((open_, open_ + 0.2, close - 0.2, close))
    return rows


# --- RSI ---------------------------------------------------------------------------------


def test_rsi_f1_buys_on_second_bottom_breaking_centre() -> None:
    closes = _rsi_closes()[:44]
    result = rsi_filter.evaluate(frame(closes))
    assert result.matched is True
    assert result.signal_type == "mua"
    assert result.details["bottoms"] == 2
    assert all(value <= 35 for value in result.details["bottom_values"])
    assert result.details["neckline"] is not None


def test_rsi_f1_holds_after_the_cross_bar() -> None:
    result = rsi_filter.evaluate(frame(_rsi_closes()))
    assert result.matched is False
    assert result.signal_type == "giu"
    assert "chưa vượt đáy trung tâm" in result.reason


def test_rsi_f1_single_bottom_is_not_enough() -> None:
    result = rsi_filter.evaluate(frame(_rsi_closes()[:40]))
    assert result.matched is False
    assert result.details["bottoms"] == 1


def test_rsi_f1_short_series_waits() -> None:
    assert rsi_filter.evaluate(frame([1, 2, 3])).reason == "không đủ dữ liệu"


def test_rsi_f1_missing_close_fails_clearly() -> None:
    result = rsi_filter.evaluate(pd.DataFrame({"open": [1.0] * 30}))
    assert result.matched is False
    assert "thiếu cột close" in result.reason


def test_rsi_bottoms_neckline_is_peak_between_bottoms() -> None:
    series = rsi(pd.Series(_rsi_closes()[:44]), 14)
    scan = rsi_bottoms(series, 35.0, order=3, lookback=60)
    assert scan["bottoms"] == 2
    assert scan["crossed"] is True
    assert scan["neckline"] == round(float(series.iloc[25:41].max()), 2)


# --- MACD --------------------------------------------------------------------------------

_MACD_CLOSES = [100.0 - 0.5 * index for index in range(40)] + [80.5, 81.5, 83.0, 85.0, 87.5]


def test_macd_f1_cross_with_improving_histogram() -> None:
    result = macd_filter.evaluate(frame(_MACD_CLOSES[:42]))
    assert result.matched is True
    assert result.signal_type == "mua"
    assert result.details["cross_ago"] == 0
    assert result.details["improving"] is True


def test_macd_f1_single_jump_is_not_two_sessions_of_improvement() -> None:
    result = macd_filter.evaluate(frame([10.0] * 40 + [12.0]))
    assert result.matched is False
    assert result.details["cross_ago"] == 0
    assert result.details["improving"] is False


def test_macd_f1_stale_cross_holds() -> None:
    result = macd_filter.evaluate(frame(_MACD_CLOSES))
    assert result.matched is False
    assert result.details["cross_ago"] is None


def test_macd_f1_no_cross_yet() -> None:
    result = macd_filter.evaluate(frame(_MACD_CLOSES[:41]))
    assert result.matched is False
    assert result.reason == "MACD chưa cắt lên Signal"


def test_macd_improving_raises_on_short_series() -> None:
    line, sig, hist = macd(pd.Series([10.0] * 36))
    try:
        macd_improving(line, sig, hist)
    except ValueError as error:
        assert "cần ít nhất" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_macd_f1_missing_close_fails_clearly() -> None:
    result = macd_filter.evaluate(pd.DataFrame({"open": [1.0] * 50}))
    assert "thiếu cột close" in result.reason


# --- Nến -------------------------------------------------------------------------------


def test_candle_f1_hammer_at_support_buys() -> None:
    rows = _decline(100, 25)
    last_close = rows[-1][3]
    rows.append((last_close - 0.5, last_close + 0.1, last_close - 3.0, last_close + 0.0))
    result = candle.evaluate(_ohlc(rows))
    assert result.details["pattern"] == "Hammer"
    assert result.matched is True
    assert result.signal_type == "mua"
    assert result.details["at_support"] is True


def test_candle_f1_hammer_away_from_support_holds() -> None:
    rows = _decline(100, 10)
    for index in range(10):
        open_ = 90 + index
        rows.append((open_, open_ + 1.2, open_ - 0.2, open_ + 1))
    rows.append((100.5, 101.0, 98.0, 100.8))
    result = candle.evaluate(_ohlc(rows))
    assert result.details["pattern"] == "Hammer"
    assert result.matched is False
    assert result.details["at_support"] is False
    assert "chưa chạm hỗ trợ" in result.reason


def test_candle_f1_ignores_bearish_patterns() -> None:
    rows = _decline(100, 10)
    for index in range(5):
        open_ = 90 + index
        rows.append((open_, open_ + 1.2, open_ - 0.2, open_ + 1))
    rows.append((96.5, 96.7, 93.0, 93.2))  # Engulfing giảm
    result = candle.evaluate(_ohlc(rows))
    assert result.details["pattern"] == "Engulfing giảm"
    assert result.matched is False
    assert candle.evaluate(_ohlc(rows), {"mode": "co_ban"}).signal_type == "ban"


def test_candle_f1_missing_low_fails_clearly() -> None:
    bars = pd.DataFrame({"open": [1.0, 2.0], "high": [2.0, 3.0], "close": [1.5, 2.5]})
    result = candle.evaluate(bars)
    assert result.matched is False
    assert "thiếu cột low" in result.reason
