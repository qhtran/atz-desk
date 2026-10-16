"""Chỉ số quý, EPS và bảng định giá đã lưu. Không quyết định mã nào vào Top 20."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from vnstock import Fundamental, Reference

from config import EPS_DIR, INDUSTRY_LEVEL, INDUSTRY_MAX_AGE_DAYS, INDUSTRY_PATH, VALUATION_PATH
from datasource.client import call


def as_ratio(value: float) -> float:
    """12,5 và 0,125 đều về dạng tỷ lệ."""
    return value / 100 if abs(value) > 1.5 else value


def ratio_quarterly(fundamental: Fundamental, ticker: str) -> pd.DataFrame:
    """Chỉ số quý. vnstock 5 chưa có ratio_quarterly, nên gọi ratio(period='quarter')."""
    equity = fundamental.equity(ticker)
    method = getattr(equity, "ratio_quarterly", None)
    if callable(method):
        return method()
    return equity.ratio(period="quarter")


def latest_metric(frame: pd.DataFrame, item_id: str) -> float | None:
    """Giá trị kỳ mới nhất của một mã chỉ số. Thiếu dữ liệu thì trả None, không điền 0."""
    if frame.empty or "id" not in frame.columns or "value" not in frame.columns:
        return None
    matched = frame.loc[frame["id"].astype(str).str.fullmatch(item_id, case=False)]
    if matched.empty:
        return None
    ordered = matched.assign(_period=matched["period"].astype(str)).sort_values("_period")
    value = pd.to_numeric(ordered["value"], errors="coerce").iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def latest_roe(frame: pd.DataFrame) -> float:
    """ROE quý mới nhất. vnstock 5 đặt mã RT_PRT_ROE, giá trị thường đã là tỷ lệ."""
    if frame.empty:
        raise ValueError("bảng chỉ số trống")
    if "id" in frame.columns and "value" in frame.columns:
        ids = frame["id"].astype(str)
        matched = frame.loc[ids.str.fullmatch(r"RT_PRT_ROE|ROE|ROEA|ROE_TTM", case=False)]
        if matched.empty and "name" in frame.columns:
            matched = frame.loc[frame["name"].astype(str).str.contains(r"\bROE\b", case=False, na=False)]
        if matched.empty:
            raise ValueError("không thấy ROE trong chỉ số quý")
        matched = matched.assign(_period=matched["period"].astype(str)).sort_values("_period")
        return as_ratio(float(matched["value"].iloc[-1]))
    roe_columns = [column for column in frame.columns if "roe" in str(column).lower()]
    if not roe_columns:
        raise ValueError("không thấy cột ROE")
    series = frame[roe_columns[0]].dropna()
    if series.empty:
        raise ValueError("ROE trống")
    return as_ratio(float(series.iloc[-1]))


def store_valuation(quotes: list[dict[str, object]]) -> None:
    if not quotes:
        return
    fresh = pd.DataFrame(quotes)
    if VALUATION_PATH.exists():
        previous = pd.read_csv(VALUATION_PATH)
        fresh = pd.concat([previous, fresh], ignore_index=True)
    fresh = fresh.drop_duplicates("Mã", keep="last")
    VALUATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(VALUATION_PATH, index=False)


def read_valuation() -> pd.DataFrame:
    if not VALUATION_PATH.exists():
        return pd.DataFrame(columns=["Mã", "P/E", "P/B"])
    stored = pd.read_csv(VALUATION_PATH)
    for column in ("Mã", "P/E", "P/B"):
        if column not in stored.columns:
            stored[column] = pd.NA
    return stored


def industry_table() -> pd.DataFrame:
    if INDUSTRY_PATH.exists():
        age = date.today() - date.fromtimestamp(INDUSTRY_PATH.stat().st_mtime)
        if age <= timedelta(days=INDUSTRY_MAX_AGE_DAYS):
            return pd.read_csv(INDUSTRY_PATH)
    listed = call(lambda: Reference().equity.list_by_industry())
    level = pd.to_numeric(listed["icb_level"], errors="coerce")
    chosen = listed.loc[level == INDUSTRY_LEVEL, ["symbol", "icb_name"]].copy()
    chosen["symbol"] = chosen["symbol"].astype(str).str.upper()
    chosen = chosen.drop_duplicates("symbol")
    INDUSTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(INDUSTRY_PATH, index=False)
    return chosen


def multiples(symbol: str) -> dict[str, object]:
    try:
        ratios = call(lambda: ratio_quarterly(Fundamental(), symbol))
    except Exception:
        return {"Mã": symbol, "P/E": None, "P/B": None}
    return {
        "Mã": symbol,
        "P/E": latest_metric(ratios, "RT_VALUE_PE"),
        "P/B": latest_metric(ratios, "RT_VALUE_PB"),
    }


def basic_eps(symbol: str) -> pd.DataFrame:
    path = EPS_DIR / f"{symbol}.csv"
    if path.exists() and date.fromtimestamp(path.stat().st_mtime) == date.today():
        return pd.read_csv(path)
    statement = call(lambda: Fundamental().equity(symbol).income_statement(period="quarter"))
    rows = statement.loc[
        statement["id"].astype(str) == "IS_BASIC_EARNINGS_PER_SHARE",
        ["period", "value"],
    ].copy()
    EPS_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False)
    return rows


def eps_growth(symbol: str) -> tuple[str, float] | None:
    series = basic_eps(symbol)
    series = series.assign(
        period=series["period"].astype(str),
        value=pd.to_numeric(series["value"], errors="coerce"),
    ).dropna(subset=["value"])
    series = series.sort_values("period")
    if series.empty:
        return None
    latest = series.iloc[-1]
    period = str(latest["period"])
    if "-Q" not in period:
        return None
    year, quarter = period.split("-Q", maxsplit=1)
    prior = f"{int(year) - 1}-Q{quarter}"
    older = series.loc[series["period"] == prior, "value"]
    if older.empty:
        return None
    base = float(older.iloc[-1])
    if base == 0:
        return None
    growth = (float(latest["value"]) - base) / abs(base)
    return period, growth


def stored_roe(symbol: str) -> float | None:
    stored = read_valuation()
    if "ROE" not in stored.columns or stored.empty:
        return None
    matched = stored.loc[stored["Mã"].astype(str).str.upper() == symbol, "ROE"]
    if matched.empty:
        return None
    value = pd.to_numeric(matched, errors="coerce").iloc[-1]
    if pd.isna(value):
        return None
    return float(value)
