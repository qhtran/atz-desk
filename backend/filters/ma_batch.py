"""Vectorized MA crossover batch (matches legacy filters.ma)."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from backend.filters._types import BatchSignal
from backend.portfolio_f3 import _ensure_legacy_path

MaKind = Literal["sma", "ema"]


def _default_params() -> dict[str, Any]:
    _ensure_legacy_path()
    from filters.base import resolve_params
    from filters.ma import FILTER

    return resolve_params(FILTER, None)


def _ma_line(close: pd.DataFrame, length: int, kind: MaKind) -> pd.DataFrame:
    if kind == "ema":
        return close.ewm(span=length, adjust=False, min_periods=length).mean()
    return close.rolling(length, min_periods=length).mean()


def _panels_close(panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for sym, bars in panels.items():
        if bars is None or bars.empty or "close" not in bars.columns:
            continue
        code = str(sym).upper()
        cols[code] = pd.to_numeric(bars["close"], errors="coerce").reset_index(drop=True)
    return pd.DataFrame(cols) if cols else pd.DataFrame()


def evaluate_ma_batch(
    panels: dict[str, pd.DataFrame],
    params: dict[str, Any] | None = None,
) -> dict[str, BatchSignal]:
    chosen = _default_params()
    if params:
        chosen.update(params)
    fast = int(chosen["fast"])
    slow = int(chosen["slow"])
    kind: MaKind = str(chosen.get("ma_type", "sma")).lower()  # type: ignore[assignment]
    if kind not in ("sma", "ema"):
        kind = "sma"

    close = _panels_close(panels)
    out: dict[str, BatchSignal] = {}
    if close.empty:
        return out

    if fast >= slow:
        msg = "MA nhanh phải nhỏ hơn MA chậm"
        for code in close.columns:
            out[code] = BatchSignal(False, "cho", msg, None)
        return out

    fast_ma = _ma_line(close, fast, kind)
    slow_ma = _ma_line(close, slow, kind)
    if len(close) < slow + 1:
        for code in close.columns:
            out[code] = BatchSignal(False, "cho", "không đủ dữ liệu", None)
        return out

    f_prev, f_last = fast_ma.iloc[-2], fast_ma.iloc[-1]
    s_prev, s_last = slow_ma.iloc[-2], slow_ma.iloc[-1]
    crossed_up = (f_prev <= s_prev) & (f_last > s_last)
    crossed_down = (f_prev >= s_prev) & (f_last < s_last)
    valid = f_last.notna() & s_last.notna() & f_prev.notna() & s_prev.notna()

    for code in close.columns:
        if not bool(valid.get(code, False)):
            out[code] = BatchSignal(False, "cho", "không đủ dữ liệu", None)
            continue
        bar_len = close[code].notna().sum()
        if bar_len < slow + 1:
            out[code] = BatchSignal(False, "cho", "không đủ dữ liệu", None)
            continue
        details = {
            "fast": float(f_last[code]),
            "slow": float(s_last[code]),
            "fast_length": fast,
            "slow_length": slow,
        }
        if bool(crossed_up.get(code, False)):
            out[code] = BatchSignal(True, "mua", f"MA{fast} cắt lên MA{slow}", details)
        elif bool(crossed_down.get(code, False)):
            out[code] = BatchSignal(True, "ban", f"MA{fast} cắt xuống MA{slow}", details)
        else:
            out[code] = BatchSignal(False, "giu", "chưa cắt MA", details)
    return out
