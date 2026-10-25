"""Catalog tiêu chí lọc F1 và map sang filter registry."""

from __future__ import annotations

from filters import load_registry
from filters.base import resolve_params
from ui.filter_criteria import CRITERIA_ROWS, F1_FILTERS, criteria_board


def test_criteria_board_has_tech_rows():
    board = criteria_board()
    assert len(board) == len(CRITERIA_ROWS)
    assert "RSI" in set(board["Tên tiêu chí"])
    assert "MACD" in set(board["Tên tiêu chí"])
    assert "Chấm điểm cố vấn 0–100" in set(board["Tên tiêu chí"])
    assert list(board.columns) == ["Nhóm", "TT", "Tên tiêu chí", "Ghi chú F1", "Bộ lọc app", "Trạng thái"]


def test_every_mapped_filter_exists_in_registry():
    registry = load_registry()
    for row in CRITERIA_ROWS:
        name = row["Bộ lọc app"].split(" ")[0]
        if name == "—":
            continue
        assert name in registry, name


def test_f1_rows_map_to_f1_mode_by_default():
    registry = load_registry()
    rows = {row["TT"]: row for row in CRITERIA_ROWS}
    for tt, (name, params) in F1_FILTERS.items():
        assert rows[tt]["Bộ lọc app"].startswith(name)
        spec = registry[name].FILTER
        assert resolve_params(spec, params)["mode"] == "f1"
        assert resolve_params(spec, None)["mode"] == "f1"
        assert rows[tt]["Trạng thái"].startswith("Đã gắn F1")
