"""Vectorized volume spike batch (matches legacy filters.volume)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.filters._types import BatchSignal
from backend.portfolio_f3 import _ensure_legacy_path


def _default_params() -> dict[str, Any]:
    _ensure_legacy_path()
    from filters.base import resolve_params
    from filters.volume import FILTER

    return resolve_params(FILTER, None)


def _panel_matrix(panels: dict[str, pd.DataFrame], column: str) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for sym, bars in panels.items():
        if bars is None or bars.empty or column not in bars.columns:
            continue
        code = str(sym).upper()
        cols[code] = pd.to_numeric(bars[column], errors="coerce").reset_index(drop=True)
    return pd.DataFrame(cols) if cols else pd.DataFrame()


def evaluate_volume_batch(
    panels: dict[str, pd.DataFrame],
    params: dict[str, Any] | None = None,
) -> dict[str, BatchSignal]:
    chosen = _default_params()
    if params:
        chosen.update(params)
    length = int(chosen["length"])
    spike = float(chosen["spike"])

    volume = _panel_matrix(panels, "volume")
    open_ = _panel_matrix(panels, "open")
    close = _panel_matrix(panels, "close")
    out: dict[str, BatchSignal] = {}
    if volume.empty or close.empty or open_.empty:
        return out

    symbols = [c for c in volume.columns if c in close.columns and c in open_.columns]
    if not symbols:
        return out

    volume = volume[symbols]
    close = close[symbols]
    open_ = open_[symbols]

    average = volume.rolling(length, min_periods=length).mean()
    avg_last = average.iloc[-1]
    vol_last = volume.iloc[-1]
    ratio = vol_last / avg_last.replace(0, pd.NA)

    bull = close.iloc[-1] > open_.iloc[-1]
    bear = close.iloc[-1] < open_.iloc[-1]
    spike_ok = ratio >= spike
    valid = avg_last.notna() & (avg_last != 0) & ratio.notna()

    for code in symbols:
        if not bool(valid.get(code, False)):
            out[code] = BatchSignal(False, "giu", "không đủ dữ liệu", None)
            continue
        r = round(float(ratio[code]), 2)
        details = {"ratio": r, "spike": spike}
        if not bool(spike_ok.get(code, False)):
            out[code] = BatchSignal(False, "giu", f"Khối lượng {r} lần trung bình", details)
        elif bool(bull.get(code, False)):
            out[code] = BatchSignal(True, "mua", f"Khối lượng đột biến {r} lần, nến tăng", details)
        elif bool(bear.get(code, False)):
            out[code] = BatchSignal(True, "ban", f"Khối lượng đột biến {r} lần, nến giảm", details)
        else:
            out[code] = BatchSignal(False, "giu", "Khối lượng đột biến nhưng nến không có hướng", details)
    return out
