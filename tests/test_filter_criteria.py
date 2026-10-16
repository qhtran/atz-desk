"""Catalog tiêu chí lọc F1."""

from __future__ import annotations

from ui.filter_criteria import CRITERIA_ROWS, criteria_board


def test_criteria_board_has_tech_rows():
    board = criteria_board()
    assert len(board) == len(CRITERIA_ROWS)
    assert "RSI" in set(board["Tên tiêu chí"])
    assert "MACD" in set(board["Tên tiêu chí"])
    assert list(board.columns) == ["Nhóm", "TT", "Tên tiêu chí", "Ghi chú F1", "Bộ lọc app", "Trạng thái"]
