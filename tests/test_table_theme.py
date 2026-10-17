"""3 variants bảng — normalize, detect signed, polish + sole dataframe entry."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ui.table_theme import (
    apply_zebra,
    container_key,
    detect_signed_columns,
    normalize_variant,
    polish_for_variant,
)

# Calls allowed only inside ui/components.py (render_data_table wrapper).
_STREAMLIT_TABLE_CALL = re.compile(
    r"\bst\.(dataframe|data_editor|table)\s*\(",
)
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "atz"
_ALLOWED_TABLE_FILE = _SRC_ROOT / "ui" / "components.py"


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


def test_no_streamlit_table_bypass_outside_wrapper() -> None:
    """Regression: mọi bảng UI phải qua render_data_table (T-110)."""
    assert _SRC_ROOT.is_dir(), f"missing src root: {_SRC_ROOT}"
    assert _ALLOWED_TABLE_FILE.is_file(), f"missing wrapper: {_ALLOWED_TABLE_FILE}"

    offenders: list[str] = []
    wrapper_hits = 0
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits = list(_STREAMLIT_TABLE_CALL.finditer(text))
        if not hits:
            continue
        if path.resolve() == _ALLOWED_TABLE_FILE.resolve():
            wrapper_hits += len(hits)
            continue
        rel = path.relative_to(_SRC_ROOT)
        for m in hits:
            line_no = text.count("\n", 0, m.start()) + 1
            offenders.append(f"{rel}:{line_no}: {m.group(0).rstrip()}")

    assert wrapper_hits >= 1, (
        "ui/components.py must call st.dataframe inside render_data_table"
    )
    assert not offenders, (
        "st.dataframe / st.data_editor / st.table outside ui/components.py:\n"
        + "\n".join(offenders)
    )
