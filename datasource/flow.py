"""Cache dòng khối ngoại và tự doanh. Cùng ngày thì đọc file, không gọi lại API."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from vnstock import Market

from config import CHART_DAYS, FLOW_DIR, HN_ZONE
from datasource.client import call


def flow_path(symbol: str, kind: str):
    return FLOW_DIR / f"{symbol.strip().upper()}_{kind}.csv"


def _today() -> date:
    return datetime.now(HN_ZONE).date()


def cache_is_fresh(path) -> bool:
    """File ghi trong ngày hôm nay thì còn dùng được."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    written = datetime.fromtimestamp(path.stat().st_mtime, HN_ZONE).date()
    return written == _today()


def fetch_flow(symbol: str, kind: str) -> pd.DataFrame:
    """Tải lịch sử. kind là foreign hoặc proprietary."""
    end = _today().isoformat()
    start = (_today() - timedelta(days=CHART_DAYS)).isoformat()
    market = Market().equity(symbol.strip().upper())
    loader = market.foreign_flow if kind == "foreign" else market.proprietary_flow
    frame = call(lambda: loader(start=start, end=end))
    if frame is None or frame.empty:
        return pd.DataFrame()
    FLOW_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(flow_path(symbol, kind), index=False)
    return frame


def load_flow(symbol: str, kind: str) -> pd.DataFrame:
    """Đọc cache nếu file được ghi hôm nay. Không thì gọi vnstock một lần."""
    path = flow_path(symbol, kind)
    if cache_is_fresh(path):
        return pd.read_csv(path)
    try:
        fresh = fetch_flow(symbol, kind)
    except Exception:
        if path.exists():
            return pd.read_csv(path)
        return pd.DataFrame()
    if fresh.empty and path.exists():
        return pd.read_csv(path)
    return fresh


def _day_key(values: pd.Series) -> pd.Series:
    stamps = pd.to_datetime(values, errors="coerce")
    if getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert(HN_ZONE)
    return stamps.dt.date


def merge_net_vol(bars: pd.DataFrame, flow: pd.DataFrame, column: str) -> pd.DataFrame:
    """Gắn net_vol theo ngày vào khung nến. Thiếu dòng thì để trống."""
    work = bars.copy()
    if flow is None or flow.empty or "net_vol" not in flow.columns or "time" not in flow.columns:
        work[column] = pd.NA
        return work
    side = flow.copy()
    side["_day"] = _day_key(side["time"])
    side["net_vol"] = pd.to_numeric(side["net_vol"], errors="coerce")
    side = side.dropna(subset=["_day"]).drop_duplicates("_day", keep="last")
    lookup = dict(zip(side["_day"], side["net_vol"]))
    work[column] = [_lookup(day, lookup) for day in _day_key(work["time"])]
    return work


def _lookup(day, lookup: dict):
    if day != day:
        return pd.NA
    return lookup.get(day, pd.NA)
