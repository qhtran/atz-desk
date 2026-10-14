"""Gọi vnstock và đọc cache OHLCV trong data/. Không chứa bộ lọc Top 20."""

from __future__ import annotations

import time
import warnings
from datetime import date, timedelta

import pandas as pd
from vnstock import Market

from config import (
    BARS_DIR,
    BARS_MAX_AGE_DAYS,
    CHART_DAYS,
    HN_ZONE,
    MARKET_INDEX,
    QUOTA_RETRIES,
    QUOTA_SLEEP_SECONDS,
)


def quota_hit(error: Exception) -> bool:
    text = str(error).lower()
    return "hạn mức" in text or "quota" in text or "per-minute" in text


def call(action):
    """Gọi API. Golden cho 500 lượt/phút nên không nghỉ giữa các lần. Hết hạn mức thì chờ rồi thử lại."""
    for attempt in range(QUOTA_RETRIES):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                return action()
        except Exception as error:
            if quota_hit(error) and attempt < QUOTA_RETRIES - 1:
                time.sleep(QUOTA_SLEEP_SECONDS)
                continue
            raise
    raise RuntimeError("Hết số lần thử sau khi chạm hạn mức.")


def day_index(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.sort_values("time").copy()
    stamps = pd.to_datetime(work["time"])
    if getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert(HN_ZONE)
    work["_day"] = stamps.dt.date
    return work


def ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Nến ngày từ KBS. Cùng giá đóng cửa với VCI, trả về nhanh hơn trên gói Golden."""
    return call(
        lambda: Market().equity(symbol).ohlcv(
            start=start,
            end=end,
            interval="1D",
            source="kbs",
        )
    )


def fresh_bars(path, start: str) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or "time" not in frame.columns:
        return None
    stamps = pd.to_datetime(frame["time"])
    newest = stamps.max()
    oldest = stamps.min()
    if pd.isna(newest) or pd.isna(oldest):
        return None
    if newest.date() < date.today() - timedelta(days=BARS_MAX_AGE_DAYS):
        return None
    if oldest.date().isoformat() > start:
        return None
    return frame


def save_bars(symbol: str, frame: pd.DataFrame) -> None:
    BARS_DIR.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["_day"], errors="ignore").to_csv(BARS_DIR / f"{symbol}.csv", index=False)


def load_bars(symbol: str, start: str) -> pd.DataFrame:
    cached = fresh_bars(BARS_DIR / f"{symbol}.csv", start)
    if cached is not None:
        return day_index(cached)
    frame = ohlcv(symbol, start, date.today().isoformat())
    save_bars(symbol, frame)
    return day_index(frame)


def load_index_bars() -> pd.DataFrame | None:
    """Nến VNINDEX cho chữ M và so sánh RS. Lỗi hoặc không có dữ liệu thì trả None."""
    start = (date.today() - timedelta(days=CHART_DAYS)).isoformat()
    path = BARS_DIR / f"{MARKET_INDEX}.csv"
    cached = fresh_bars(path, start)
    if cached is not None:
        return day_index(cached)
    end = date.today().isoformat()
    attempts = [
        lambda: Market().index(MARKET_INDEX).ohlcv(start=start, end=end, interval="1D"),
        lambda: Market().equity(MARKET_INDEX).ohlcv(start=start, end=end, interval="1D", source="kbs"),
        lambda: Market().equity(MARKET_INDEX).ohlcv(start=start, end=end, interval="1D"),
    ]
    for attempt in attempts:
        try:
            frame = call(attempt)
            if frame is not None and not frame.empty and "close" in frame.columns:
                save_bars(MARKET_INDEX, frame)
                return day_index(frame)
        except Exception:
            continue
    return None
