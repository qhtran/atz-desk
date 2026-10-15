"""Nến giả cho test filter. Không đọc file và không gọi mạng."""

from __future__ import annotations

import pandas as pd


def frame(closes: list[float], volumes: list[float] | None = None, opens: list[float] | None = None) -> pd.DataFrame:
    size = len(closes)
    volume = volumes or [1000.0] * size
    open_ = opens or closes
    return pd.DataFrame(
        {
            "time": [f"2026-01-{day:02d}" for day in range(1, size + 1)],
            "open": open_,
            "high": [max(a, b) + 0.5 for a, b in zip(open_, closes)],
            "low": [min(a, b) - 0.5 for a, b in zip(open_, closes)],
            "close": closes,
            "volume": volume,
        }
    )
