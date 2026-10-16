"""StockItem chuẩn (kiểu FireAnt) + bảng realtime kèm sparkline.

Giá OHLCV = nghìn đồng; quote realtime = VND. Sparkline quy về nghìn đồng.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from config import SPARKLINE_BARS, THOUSAND_VND
from datasource.spark_series import load_sparklines


@dataclass
class StockItem:
    ticker: str
    price: float | None = None
    change: float | None = None
    change_percent: float | None = None
    volume: float | None = None
    ref_price: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    source: str = ""
    company_name: str = ""
    market_cap: float | None = None
    sparkline: list[float] = field(default_factory=list)
    unit: str = "vnd"  # "vnd" | "k"

    @property
    def is_positive(self) -> bool:
        if self.change_percent is not None:
            return self.change_percent >= 0
        if self.change is not None:
            return self.change >= 0
        return True

    @classmethod
    def from_quote(cls, quote: dict[str, Any], sparkline: list[float] | None = None) -> StockItem:
        symbol = str(quote.get("symbol") or "").strip().upper()
        return cls(
            ticker=symbol,
            price=_float(quote.get("price")),
            change=_float(quote.get("change")),
            change_percent=_float(quote.get("change_pct")),
            volume=_float(quote.get("volume")),
            ref_price=_float(quote.get("ref_price")),
            open=_float(quote.get("open")),
            high=_float(quote.get("high")),
            low=_float(quote.get("low")),
            source=str(quote.get("source") or "").lower(),
            sparkline=list(sparkline or []),
            unit="vnd",
        )

    def with_live_on_spark(self) -> StockItem:
        if self.price is None or not self.sparkline:
            return self
        live_k = self.price / THOUSAND_VND if self.unit == "vnd" else self.price
        series = list(self.sparkline)
        if not series or abs(series[-1] - live_k) > 1e-6:
            series.append(live_k)
        return StockItem(
            ticker=self.ticker,
            price=self.price,
            change=self.change,
            change_percent=self.change_percent,
            volume=self.volume,
            ref_price=self.ref_price,
            open=self.open,
            high=self.high,
            low=self.low,
            source=self.source,
            company_name=self.company_name,
            market_cap=self.market_cap,
            sparkline=series,
            unit=self.unit,
        )


def _float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def items_from_quotes(
    quotes: list[dict[str, Any]],
    *,
    bars_dir: Path | None = None,
    spark_bars: int = SPARKLINE_BARS,
) -> list[StockItem]:
    live: dict[str, float] = {}
    for q in quotes:
        sym = str(q.get("symbol") or "").strip().upper()
        px = _float(q.get("price"))
        if sym and px is not None:
            live[sym] = px
    sparks = load_sparklines(list(live), bars_dir=bars_dir, n=spark_bars, live_prices_vnd=live)
    items = []
    for q in quotes:
        code = str(q.get("symbol") or "").strip().upper()
        item = StockItem.from_quote(q, sparkline=sparks.get(code, []))
        if item.ticker:
            items.append(item)
    items.sort(key=lambda x: x.ticker)
    return items


def realtime_board_frame(
    quote_rows: list[dict[str, Any]],
    *,
    bars_dir: Path | None = None,
    spark_bars: int = SPARKLINE_BARS,
) -> pd.DataFrame:
    """Ghép dòng bảng giá (đã có stale) với cột Xu hướng (list[float])."""
    symbols = [str(r.get("Mã") or "").strip().upper() for r in quote_rows if r.get("Mã")]
    live: dict[str, float] = {}
    for row in quote_rows:
        code = str(row.get("Mã") or "").strip().upper()
        px = _float(row.get("Giá"))
        if code and px is not None:
            live[code] = px
    sparks = load_sparklines(symbols, bars_dir=bars_dir, n=spark_bars, live_prices_vnd=live)
    rows = []
    for row in quote_rows:
        code = str(row.get("Mã") or "").strip().upper()
        public = {k: v for k, v in row.items() if not str(k).startswith("_")}
        public["Xu hướng"] = sparks.get(code, [])
        rows.append(public)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    cols = [c for c in frame.columns if c != "Xu hướng"]
    if "%" in cols:
        i = cols.index("%") + 1
        ordered = cols[:i] + ["Xu hướng"] + cols[i:]
    else:
        ordered = cols + ["Xu hướng"]
    return frame[ordered]
