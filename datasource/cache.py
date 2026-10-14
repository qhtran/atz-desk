"""Đọc bảng Top 20 đã ghi ở data/top20_cache.csv."""

from __future__ import annotations

import pandas as pd

from config import CACHE_PATH, COLUMNS, SCAN_UNIVERSE_PATH


def read_cache() -> pd.DataFrame:
    if not CACHE_PATH.exists():
        return pd.DataFrame(columns=COLUMNS)
    board = pd.read_csv(CACHE_PATH)
    missing = [column for column in COLUMNS if column not in board.columns]
    if missing:
        raise ValueError(f"thiếu cột {', '.join(missing)}")
    return board[COLUMNS]


def read_universe() -> pd.DataFrame | None:
    """Mọi mã quét được, kể cả mã không vào Top 20. Chưa có file thì trả None."""
    if not SCAN_UNIVERSE_PATH.exists():
        return None
    board = pd.read_csv(SCAN_UNIVERSE_PATH)
    missing = [column for column in COLUMNS if column not in board.columns]
    if missing:
        raise ValueError(f"thiếu cột {', '.join(missing)}")
    return board[COLUMNS]
