"""Ngữ cảnh lịch sử: nến ngày từ loader của app (data/ohlcv), cache trong bộ nhớ, ghép quote live làm nến hôm nay."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta

import pandas as pd

from filter_runner.log import log

FLOW_COLUMNS = {"foreign": "foreign_net_vol", "proprietary": "prop_net_vol"}


def app_loaders(remote: bool):
    """Loader của app. remote=False: chỉ đọc CSV trong data/ohlcv (không gọi API)."""
    from config import BARS_DIR
    from datasource.client import day_index, fresh_bars, load_bars, load_index_bars

    def bars(symbol: str, start: str):
        if remote:
            return load_bars(symbol, start)
        path = BARS_DIR / f"{symbol}.csv"
        frame = pd.read_csv(path) if path.exists() else None
        return day_index(frame) if frame is not None and not frame.empty else None

    def index():
        if remote:
            return load_index_bars()
        frame = fresh_bars(BARS_DIR / "VNINDEX.csv", "1900-01-01")
        return day_index(frame) if frame is not None else None

    def flow(symbol: str, kind: str):
        from datasource.flow import flow_path, load_flow
        if remote:
            return load_flow(symbol, kind)
        path = flow_path(symbol, kind)
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    return bars, index, flow


class HistoryCache:
    def __init__(self, days: int, ttl: float, price_scale: float, loaders=None, remote: bool = True,
                 clock=time.monotonic):
        self.days, self.ttl, self.scale, self.clock = days, ttl, price_scale, clock
        self._bars_fn, self._index_fn, self._flow_fn = loaders or app_loaders(remote)
        self._bars: dict[str, tuple[float, pd.DataFrame | None]] = {}
        self._index: tuple[float, pd.DataFrame | None] | None = None

    def _fresh(self, stamp: float) -> bool:
        return self.clock() - stamp < self.ttl

    def base(self, symbol: str, flows: set[str]) -> pd.DataFrame | None:
        key = symbol + "|" + ",".join(sorted(flows))
        hit = self._bars.get(key)
        if hit and self._fresh(hit[0]):
            return hit[1]
        start = (date.today() - timedelta(days=self.days)).isoformat()
        started = time.monotonic()
        try:
            frame = self._bars_fn(symbol, start)
            if frame is not None and not frame.empty:
                from datasource.flow import merge_net_vol
                for kind in sorted(flows):
                    if kind in FLOW_COLUMNS:
                        frame = merge_net_vol(frame, self._flow_fn(symbol, kind), FLOW_COLUMNS[kind])
        except Exception as error:  # noqa: BLE001
            log("HISTORY", f"history load failed: {type(error).__name__}: {error}", logging.WARNING, symbol=symbol)
            frame = hit[1] if hit else None
        self._bars[key] = (self.clock(), frame)
        log("HISTORY", f"loaded bars={0 if frame is None else len(frame)} flows={sorted(flows)}", symbol=symbol,
            latency_ms=int((time.monotonic() - started) * 1000))
        return frame

    def index_bars(self):
        if self._index and self._fresh(self._index[0]):
            return self._index[1]
        try:
            frame = self._index_fn()
        except Exception as error:  # noqa: BLE001
            log("HISTORY", f"index load failed: {error}", logging.WARNING, symbol="VNINDEX")
            frame = self._index[1] if self._index else None
        self._index = (self.clock(), frame)
        return frame

    def with_quote(self, base: pd.DataFrame, quote: dict) -> pd.DataFrame:
        """Thay/thêm nến hôm nay bằng giá live (đổi đơn vị VND -> nghìn đồng)."""
        def px(name):
            value = quote.get(name)
            return float(value) * self.scale if value not in (None, "") else None
        price = px("price")
        if price is None:
            return base
        ts = pd.Timestamp(quote.get("timestamp") or datetime.now().isoformat())
        work = base.copy()
        last_day = pd.to_datetime(work["time"].iloc[-1])
        same_day = last_day.date() == ts.date()
        row = work.iloc[-1].to_dict() if same_day else {c: work[c].iloc[-1] for c in work.columns}
        row.update({"time": work["time"].iloc[-1] if same_day else ts, "close": price,
                    "open": px("open") or (row.get("open") if same_day else price),
                    "high": max(filter(None, [px("high"), price])), "low": min(filter(None, [px("low"), price]))})
        volume = quote.get("volume")
        if volume not in (None, ""):
            row["volume"] = float(volume)
        elif not same_day:
            row["volume"] = work["volume"].iloc[-1]   # quote chưa có volume (Module 1) -> giữ volume phiên trước
        if "_day" in work.columns:
            row["_day"] = ts.date()
        if same_day:
            work.iloc[-1] = pd.Series(row)
            return work
        return pd.concat([work, pd.DataFrame([row])], ignore_index=True)
