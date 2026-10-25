"""Bảng Tiêu chí lọc (F1 mục 7) — catalog mentor, map sang filter hiện có.

Không thay engine lọc. Mục 5–6 / phần II còn thiếu mô tả mentor thì ghi chú.
"Bộ lọc app" bắt đầu bằng tên filter trong registry (filters/*.py); F1_FILTERS là
map hàng → (filter, params) mà filter runner / engine chạy.
"""

from __future__ import annotations

import pandas as pd

CRITERIA_ROWS = (
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "1",
        "Tên tiêu chí": "Nến Nhật",
        "Ghi chú F1": "Đảo chiều tại hỗ trợ; mạnh / TB / yếu / 3 đáy",
        "Bộ lọc app": "candle (mode f1)",
        "Trạng thái": "Đã gắn F1: Engulfing tăng / Hammer chạm hỗ trợ 6 tháng; mạnh/TB/yếu chưa có",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "2",
        "Tên tiêu chí": "RSI",
        "Ghi chú F1": "2–3 đáy vùng 30, vượt đáy trung tâm",
        "Bộ lọc app": "rsi (mode f1)",
        "Trạng thái": "Đã gắn F1: ≥2 đáy RSI ≤ 30+5, vượt đáy trung tâm RSI",
    },
    {
        "Nhóm": "I. Chỉ tiêu kỹ thuật",
        "TT": "3",
        "Tên tiêu chí": "MACD",
        "Ghi chú F1": "Cắt lên Signal + histogram cải thiện ≥ 2 phiên",
        "Bộ lọc app": "macd (mode f1)",
        "Trạng thái": "Đã gắn F1: cắt lên Signal ≤3 phiên + histogram tăng ≥2 phiên",
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
        "Nhóm": "III. Cố vấn",
        "TT": "7",
        "Tên tiêu chí": "Chấm điểm cố vấn 0–100",
        "Ghi chú F1": "Xu hướng (MA) + dòng tiền (KN/KL) + KT ngắn (RSI/BB/MACD)",
        "Bộ lọc app": "advisor",
        "Trạng thái": "Engine + UI batch; debug overlay FILTER-ADVISOR",
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

# Hàng F1 đã gắn logic: TT -> (tên filter trong registry, params gửi cho evaluate).
F1_FILTERS = {
    "1": ("candle", {"mode": "f1"}),
    "2": ("rsi", {"mode": "f1"}),
    "3": ("macd", {"mode": "f1"}),
}


def criteria_board() -> pd.DataFrame:
    return pd.DataFrame(list(CRITERIA_ROWS))
