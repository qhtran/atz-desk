"""Bộ lọc Top 20: RS 3 tháng, rồi ROE và thanh khoản. Ngưỡng nằm trong config."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from vnstock import Fundamental

from config import (
    COLUMNS, MIN_AVG_VOLUME, MIN_BARS, MIN_ROE, RS_FILTER_OFF, RS_LOOKBACK_DAYS, SCAN_DAYS,
    SCAN_UNIVERSE_PATH, TOP_N, UNIVERSE, VOLUME_AVG, WORKERS,
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


def apply_filter(
    board: pd.DataFrame,
    min_roe_pct: float,
    min_volume: float,
    min_rs: float,
    top_n: int,
) -> pd.DataFrame:
    """Lọc bảng đã quét. Không gọi API. Mặc định ROE 12%, KL 100.000, RS tắt, lấy 20 mã."""
    if board.empty:
        return pd.DataFrame(columns=COLUMNS)
    work = board.copy()
    work["ROE (%)"] = pd.to_numeric(work["ROE (%)"], errors="coerce")
    work["KLGD TB 20 phiên"] = pd.to_numeric(work["KLGD TB 20 phiên"], errors="coerce")
    work["RS 3 tháng (%)"] = pd.to_numeric(work["RS 3 tháng (%)"], errors="coerce")
    work = work.loc[work["ROE (%)"] >= min_roe_pct]
    work = work.loc[work["KLGD TB 20 phiên"] >= min_volume]
    if min_rs > RS_FILTER_OFF:
        work = work.loc[work["RS 3 tháng (%)"] >= min_rs]
    if work.empty:
        return pd.DataFrame(columns=COLUMNS)
    return (
        work.sort_values("RS 3 tháng (%)", ascending=False)
        .head(top_n)[COLUMNS]
        .reset_index(drop=True)
    )


def scan_one(
    symbol: str,
    start: str,
    end: str,
    min_volume: float = MIN_AVG_VOLUME,
    min_roe: float = MIN_ROE,
) -> tuple[dict[str, object] | None, str | None, dict[str, object] | None, dict[str, object] | None]:
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
        return None, f"{symbol}: {error}", None, None
    record = {
        "Mã": symbol,
        "Giá": price,
        "RS 3 tháng (%)": strength,
        "ROE (%)": round(roe * 100, 2),
        "KLGD TB 20 phiên": volume,
    }
    passed = volume >= min_volume and roe >= min_roe
    return (record if passed else None), None, quote, record


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
            _passed, error, quote, record = future.result()
            if error:
                errors.append(error)
            if record is not None:
                rows.append(record)
            if quote is not None:
                quotes.append(quote)
    store_valuation(quotes)
    if rows:
        SCAN_UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows)[COLUMNS].to_csv(SCAN_UNIVERSE_PATH, index=False)
    board = apply_filter(
        pd.DataFrame(rows),
        min_roe_pct=MIN_ROE * 100,
        min_volume=MIN_AVG_VOLUME,
        min_rs=RS_FILTER_OFF,
        top_n=TOP_N,
    )
    return board, errors
