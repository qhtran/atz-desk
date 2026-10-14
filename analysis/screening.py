"""Bộ lọc Top 20: RS 3 tháng, rồi ROE và thanh khoản. Ngưỡng nằm trong config."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from vnstock import Fundamental

from config import (
    COLUMNS, MIN_AVG_VOLUME, MIN_BARS, MIN_ROE, RS_LOOKBACK_DAYS, SCAN_DAYS, TOP_N,
    UNIVERSE, VOLUME_AVG, WORKERS,
)
from datasource.client import call, day_index, ohlcv, save_bars
from datasource.fundamentals import latest_metric, latest_roe, ratio_quarterly, store_valuation


def price_stats(bars: pd.DataFrame) -> tuple[float, float, float]:
    if len(bars) < MIN_BARS:
        raise ValueError(f"chưa đủ {MIN_BARS} phiên")
    anchor = bars["_day"].iloc[-1] - timedelta(days=RS_LOOKBACK_DAYS)
    history = bars.loc[bars["_day"] <= anchor]
    base = float(history["close"].iloc[-1] if not history.empty else bars["close"].iloc[0])
    last = float(bars["close"].iloc[-1])
    if base == 0:
        raise ValueError("giá nền bằng 0")
    strength = round((last / base - 1) * 100, 2)
    volume = round(float(bars["volume"].tail(VOLUME_AVG).mean()), 0)
    return last, strength, volume


def scan_one(
    symbol: str, start: str, end: str
) -> tuple[dict[str, object] | None, str | None, dict[str, object] | None]:
    try:
        bars = day_index(ohlcv(symbol, start, end))
        save_bars(symbol, bars)
        price, strength, volume = price_stats(bars)
        ratios = call(lambda: ratio_quarterly(Fundamental(), symbol))
        roe = latest_roe(ratios)
        quote = {
            "Mã": symbol,
            "P/E": latest_metric(ratios, "RT_VALUE_PE"),
            "P/B": latest_metric(ratios, "RT_VALUE_PB"),
            "ROE": roe,
        }
    except Exception as error:
        return None, f"{symbol}: {error}", None
    if volume < MIN_AVG_VOLUME or roe < MIN_ROE:
        return None, None, quote
    return (
        {
            "Mã": symbol,
            "Giá": price,
            "RS 3 tháng (%)": strength,
            "ROE (%)": round(roe * 100, 2),
            "KLGD TB 20 phiên": volume,
        },
        None,
        quote,
    )


def scan_top20(on_progress=None) -> tuple[pd.DataFrame, list[str]]:
    """Quét giá và ROE song song. on_progress(done, total) nếu giao diện muốn thanh tiến độ."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows: list[dict[str, object]] = []
    errors: list[str] = []
    quotes: list[dict[str, object]] = []
    start = (date.today() - timedelta(days=SCAN_DAYS)).isoformat()
    end = date.today().isoformat()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(scan_one, symbol, start, end) for symbol in UNIVERSE]
        for index, future in enumerate(as_completed(futures), start=1):
            if on_progress is not None:
                on_progress(index, len(UNIVERSE))
            row, error, quote = future.result()
            if error:
                errors.append(error)
            elif row is not None:
                rows.append(row)
            if quote is not None:
                quotes.append(quote)
    store_valuation(quotes)
    if not rows:
        return pd.DataFrame(columns=COLUMNS), errors
    board = pd.DataFrame(rows).sort_values("RS 3 tháng (%)", ascending=False).head(TOP_N)
    return board[COLUMNS].reset_index(drop=True), errors
