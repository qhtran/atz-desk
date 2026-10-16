"""Đọc bảng Top 20 đã lưu (SQLite, bảng top20_snapshot)."""

from __future__ import annotations

import pandas as pd

from config import COLUMNS, SCAN_UNIVERSE_PATH
from datasource import top20_store


def read_cache() -> pd.DataFrame:
    """Top 20 mới nhất từ SQLite. "Giá" theo nghìn đồng."""
    board, _ = top20_store.load_latest()
    return board


def has_saved_top20() -> bool:
    try:
        return not read_cache().empty
    except Exception:  # noqa: BLE001
        return False


def read_universe() -> pd.DataFrame | None:
    """Mọi mã quét được, kể cả mã không vào Top 20. Chưa có file thì trả None."""
    if not SCAN_UNIVERSE_PATH.exists():
        return None
    board = pd.read_csv(SCAN_UNIVERSE_PATH)
    missing = [column for column in COLUMNS if column not in board.columns]
    if missing:
        raise ValueError(f"thiếu cột {', '.join(missing)}")
    return board[COLUMNS]
