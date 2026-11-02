from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BatchSignal:
    matched: bool
    signal_type: str
    reason: str
    details: dict[str, Any] | None = None


def panels_to_close_matrix(panels: dict[str, Any]) -> tuple[Any, list[str]]:
    """Wide close matrix (columns = symbols); skips empty / no close."""
    import pandas as pd

    cols: dict[str, pd.Series] = {}
    order: list[str] = []
    for sym in sorted(panels.keys()):
        bars = panels[sym]
        if bars is None or getattr(bars, "empty", True):
            continue
        if "close" not in bars.columns:
            continue
        close = pd.to_numeric(bars["close"], errors="coerce")
        if close.notna().sum() == 0:
            continue
        code = str(sym).upper()
        cols[code] = close.reset_index(drop=True)
        order.append(code)
    if not cols:
        return pd.DataFrame(), []
    return pd.DataFrame(cols), order
