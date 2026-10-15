"""KQKD quý: lợi nhuận sau thuế từ báo cáo kết quả kinh doanh (vnstock Gold)."""

from __future__ import annotations

from datetime import date

import pandas as pd
from vnstock import Fundamental

import config
from datasource.client import call

# Lợi nhuận sau thuế TNDN — metric chính cho cột KQKD.
METRIC_ID = "IS_NET_PROFIT_AFTER_TAX"
METRIC_LABEL = "LNST"


def _format_billion(value: float) -> str:
    """Hiển thị tỷ VND, ví dụ 2570.3 tỷ."""
    billions = value / 1_000_000_000
    if abs(billions) >= 100:
        return f"{billions:,.0f} tỷ"
    if abs(billions) >= 10:
        return f"{billions:,.1f} tỷ"
    return f"{billions:,.2f} tỷ"


def _load_statement(symbol: str) -> pd.DataFrame:
    path = config.KQKD_DIR / f"{symbol.upper()}.csv"
    if path.exists() and date.fromtimestamp(path.stat().st_mtime) == date.today():
        return pd.read_csv(path)
    statement = call(lambda: Fundamental().equity(symbol).income_statement(period="quarter"))
    rows = statement.loc[
        statement["id"].astype(str) == METRIC_ID,
        ["period", "value"],
    ].copy()
    config.KQKD_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False)
    return rows


def quarterly_net_profit(symbol: str) -> tuple[str, float, str, float] | None:
    """Trả (kỳ hiện tại, LNST, kỳ cùng kỳ năm trước, LNST cùng kỳ) hoặc None."""
    try:
        series = _load_statement(symbol)
    except Exception:
        return None
    if series is None or series.empty:
        return None
    work = series.assign(
        period=series["period"].astype(str),
        value=pd.to_numeric(series["value"], errors="coerce"),
    ).dropna(subset=["value"])
    work = work.sort_values("period")
    if work.empty:
        return None
    latest = work.iloc[-1]
    period = str(latest["period"])
    if "-Q" not in period:
        return None
    year, quarter = period.split("-Q", maxsplit=1)
    try:
        prior = f"{int(year) - 1}-Q{quarter}"
    except ValueError:
        return None
    older = work.loc[work["period"] == prior, "value"]
    if older.empty:
        return None
    return period, float(latest["value"]), prior, float(older.iloc[-1])


def kqkd_cells(symbol: str) -> tuple[str, str]:
    """Hai ô hiển thị: quý hiện tại và quý cùng kỳ. Lỗi thì '—'."""
    found = quarterly_net_profit(symbol)
    if found is None:
        return "—", "—"
    period, current, prior, older = found
    return (
        f"{_format_billion(current)} ({period})",
        f"{_format_billion(older)} ({prior})",
    )
