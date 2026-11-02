"""Vectorized Bollinger batch (matches legacy filters.bollinger co_ban rules)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.filters._types import BatchSignal
from backend.portfolio_f3 import _ensure_legacy_path


def _default_params() -> dict[str, Any]:
    _ensure_legacy_path()
    import config as C
    from filters.bollinger import FILTER
    from filters.base import resolve_params

    return resolve_params(FILTER, None)


def _bollinger_columns(close: pd.DataFrame, length: int, k: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    mid = close.rolling(length, min_periods=length).mean()
    std = close.rolling(length, min_periods=length).std(ddof=0)
    lower = mid - k * std
    upper = mid + k * std
    return lower, mid, upper


def evaluate_bollinger_batch(
    panels: dict[str, pd.DataFrame],
    params: dict[str, Any] | None = None,
) -> dict[str, BatchSignal]:
    chosen = _default_params()
    if params:
        chosen.update(params)
    length = int(chosen["length"])
    k = float(chosen["k"])

    out: dict[str, BatchSignal] = {}
    cols: dict[str, pd.Series] = {}
    for sym, bars in panels.items():
        if bars is None or bars.empty or "close" not in bars.columns:
            continue
        code = str(sym).upper()
        cols[code] = pd.to_numeric(bars["close"], errors="coerce").reset_index(drop=True)

    if not cols:
        return out

    close = pd.DataFrame(cols)
    lower, _mid, upper = _bollinger_columns(close, length, k)
    price = close.iloc[-1]
    low = lower.iloc[-1]
    up = upper.iloc[-1]

    valid = low.notna() & up.notna() & price.notna()
    flat = valid & (low == up)
    buy = valid & ~flat & (price <= low)
    sell = valid & ~flat & (price >= up)
    hold = valid & ~flat & ~buy & ~sell

    for code in close.columns:
        if code not in valid.index or not bool(valid[code]):
            out[code] = BatchSignal(False, "giu", "không đủ dữ liệu", None)
            continue
        p = float(price[code])
        lo = float(low[code])
        hi = float(up[code])
        details = {"close": p, "lower": round(lo, 4), "upper": round(hi, 4)}
        if bool(flat[code]):
            out[code] = BatchSignal(False, "giu", "dải Bollinger bằng nhau", details)
        elif bool(buy[code]):
            out[code] = BatchSignal(True, "mua", "Giá chạm dải Bollinger dưới", details)
        elif bool(sell[code]):
            out[code] = BatchSignal(True, "ban", "Giá chạm dải Bollinger trên", details)
        elif bool(hold[code]):
            out[code] = BatchSignal(False, "giu", "Giá nằm trong dải Bollinger", details)
        else:
            out[code] = BatchSignal(False, "giu", "Giá nằm trong dải Bollinger", details)
    return out
