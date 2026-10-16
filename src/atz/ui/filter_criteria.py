"""Bảng Tiêu chí lọc (F1 mục 7) — catalog mentor, map sang filter hiện có.

Không thay engine lọc. Mục 5–6 / phần II còn thiếu mô tả mentor thì ghi chú.
"""

from __future__ import annotations

import pandas as pd

CRITERIA_ROWS = (
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "1",
        "Tên tiêu chí": "Nến Nhật",
        "Ghi chú F1": "Đảo chiều tại hỗ trợ; mạnh / TB / yếu / 3 đáy",
        "Bộ lọc app": "candle (Nến đơn)",
        "Trạng thái": "Có filter — logic F1 đầy đủ chưa gắn",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "2",
        "Tên tiêu chí": "RSI",
        "Ghi chú F1": "2–3 đáy vùng 30, vượt đáy trung tâm",
        "Bộ lọc app": "rsi",
        "Trạng thái": "Có filter",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "3",
        "Tên tiêu chí": "MACD",
        "Ghi chú F1": "Cắt lên Signal + histogram cải thiện ≥ 2 phiên",
        "Bộ lọc app": "macd",
        "Trạng thái": "Có filter",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "4",
        "Tên tiêu chí": "Các đường MA",
        "Ghi chú F1": "Yếu / mạnh / rất mạnh theo MA5/10/20/50",
        "Bộ lọc app": "ma",
        "Trạng thái": "Có filter",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "5",
        "Tên tiêu chí": "Bollinger",
        "Ghi chú F1": "(chưa mô tả trong bản F1 đã convert)",
        "Bộ lọc app": "bollinger",
        "Trạng thái": "Có filter — chờ mentor",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "6",
        "Tên tiêu chí": "Mây Ichimoku",
        "Ghi chú F1": "(chưa mô tả)",
        "Bộ lọc app": "ichimoku",
        "Trạng thái": "Có filter — chờ mentor",
    },
    {
        "Nhóm": "II. Chỉ báo mẫu hình",
        "TT": "—",
        "Tên tiêu chí": "(doc bị cắt)",
        "Ghi chú F1": "Cần mentor bổ sung",
        "Bộ lọc app": "—",
        "Trạng thái": "Chưa có",
    },
)


def criteria_board() -> pd.DataFrame:
    return pd.DataFrame(list(CRITERIA_ROWS))
