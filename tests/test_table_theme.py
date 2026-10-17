"""3 variants bảng — normalize, detect signed, polish."""

from __future__ import annotations

import pandas as pd

from ui.table_theme import (
    apply_zebra,
    container_key,
    detect_signed_columns,
    normalize_variant,
    polish_for_variant,
)


def test_normalize_variant() -> None:
    assert normalize_variant("realtime") == "realtime"
    assert normalize_variant("COMPACT") == "compact"
    assert normalize_variant("weird") == "analytical"


def test_container_key_safe() -> None:
    assert container_key("analytical", "top5_Ngành A") == "atz_tbl_analytical_top5_Ng_nh_A"


def test_detect_signed_columns() -> None:
    cols = detect_signed_columns(["Mã", "Giá", "%", "Lãi/lỗ thương vụ", "Filter"])
    assert "%" in cols and "Lãi/lỗ thương vụ" in cols
    assert "Mã" not in cols


def test_polish_analytical_colors_and_zebra() -> None:
    frame = pd.DataFrame({"Mã": ["A", "B"], "%": [1.5, -2.0], "X": [1, 2]})
    styled = polish_for_variant(frame, "analytical")
    assert type(styled).__name__ == "Styler"
    # zebra không làm mất dữ liệu
    assert list(styled.data["Mã"]) == ["A", "B"]


def test_polish_realtime_passthrough() -> None:
    frame = pd.DataFrame({"Mã": ["A"], "Giá": [1]})
    assert polish_for_variant(frame, "realtime") is frame


def test_apply_zebra_len() -> None:
    frame = pd.DataFrame({"a": [1, 2, 3]})
    styled = apply_zebra(frame.style)
    assert len(styled.data) == 3
