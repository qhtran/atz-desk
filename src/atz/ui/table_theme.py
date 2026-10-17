"""3 variants bảng atz — một đường style (FireAnt tokens + density CSS).

Variants: ``realtime`` | ``analytical`` | ``compact``.
Mọi chỗ hiển thị bảng nên đi qua ``ui.components.render_data_table``.
"""

from __future__ import annotations

import re
from typing import Any, Literal

import pandas as pd

from ui.theme_tokens import BG_CARD, FIREANT_CSS, css_signed_number, css_signed_text

TableVariant = Literal["realtime", "analytical", "compact"]
VARIANTS: tuple[str, ...] = ("realtime", "analytical", "compact")

# Zebra nhẹ — tránh nuốt chữ Δ xanh/đỏ trên nền tối (T-153 / inbox §4.5).
ZEBRA_ODD = f"{BG_CARD}40"

# Cột hay mang dấu Δ / PnL — analytical tự tô nếu có trong frame.
SIGNED_COL_HINTS = (
    "%",
    "+/-",
    "Δ",
    "Lãi/lỗ",
    "Lãi/lỗ thương vụ",
    "Lãi/lỗ (VND)",
    "ROE (%)",
    "RS 3 tháng (%)",
    "Tăng/giảm (điểm/%)",
    "Xu hướng ngày",
)

_TABLE_VARIANT_CSS = f"""
<style>
/* Base: mọi dataframe atz */
[class*="st-key-atz_tbl_"] [data-testid="stDataFrame"] {{
  font-variant-numeric: tabular-nums;
}}
/* realtime — siêu dày */
[class*="st-key-atz_tbl_realtime"] [data-testid="stDataFrame"] td,
[class*="st-key-atz_tbl_realtime"] [data-testid="stDataFrame"] th {{
  padding-top: 0.15rem !important;
  padding-bottom: 0.15rem !important;
}}
/* analytical — vừa + zebra đã tô qua Styler */
[class*="st-key-atz_tbl_analytical"] [data-testid="stDataFrame"] td,
[class*="st-key-atz_tbl_analytical"] [data-testid="stDataFrame"] th {{
  padding-top: 0.35rem !important;
  padding-bottom: 0.35rem !important;
}}
/* compact — thu nhỏ (sidebar / ghim / alerts) */
[class*="st-key-atz_tbl_compact"] [data-testid="stDataFrame"] {{
  font-size: 0.85rem;
}}
[class*="st-key-atz_tbl_compact"] [data-testid="stDataFrame"] td,
[class*="st-key-atz_tbl_compact"] [data-testid="stDataFrame"] th {{
  padding-top: 0.12rem !important;
  padding-bottom: 0.12rem !important;
}}
/* zebra fallback nhẹ (không đụng cột Δ — Styler skip signed) */
[class*="st-key-atz_tbl_analytical"] [data-testid="stDataFrame"] tbody tr:nth-child(even) {{
  background-color: {ZEBRA_ODD};
}}
</style>
"""


def normalize_variant(value: object) -> TableVariant:
    text = str(value or "analytical").strip().lower()
    if text in VARIANTS:
        return text  # type: ignore[return-value]
    return "analytical"


def container_key(variant: TableVariant, key: str | None) -> str:
    """Key hợp lệ cho st.container → class st-key-atz_tbl_*."""
    raw = f"atz_tbl_{variant}_{key or 'anon'}"
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)[:64]


def inject_table_theme() -> None:
    """Inject FireAnt + density CSS một lần / session."""
    import streamlit as st

    if st.session_state.get("_atz_table_theme"):
        return
    st.markdown(FIREANT_CSS + _TABLE_VARIANT_CSS, unsafe_allow_html=True)
    st.session_state["_atz_table_theme"] = True


def unwrap_frame(data: Any) -> pd.DataFrame | None:
    frame = getattr(data, "data", data)
    return frame if isinstance(frame, pd.DataFrame) else None


def is_styler(data: Any) -> bool:
    return type(data).__name__ == "Styler" or hasattr(data, "data") and type(data).__module__.startswith("pandas")


def detect_signed_columns(columns: list[str]) -> list[str]:
    found: list[str] = []
    for name in columns:
        if name in SIGNED_COL_HINTS:
            found.append(name)
            continue
        lower = name.casefold()
        if any(h.casefold() in lower for h in ("lãi", "lỗ", "pnl", "%", "+/-", "tăng/giảm", "roe", "rs ")):
            if name not in found:
                found.append(name)
    return found


def apply_zebra(styler: Any, *, skip_cols: list[str] | None = None) -> Any:
    """Zebra nhẹ; bỏ nền trên cột signed (Δ/%/PnL) để chữ màu đọc được."""
    frame = styler.data
    order = {idx: i for i, idx in enumerate(frame.index)}
    skip = set(skip_cols or [])

    def band(row: pd.Series) -> list[str]:
        odd = order.get(row.name, 0) % 2 == 1
        tone = f"background-color: {ZEBRA_ODD}" if odd else ""
        styles: list[str] = []
        for name in row.index:
            if name in skip:
                styles.append("")
            else:
                styles.append(tone)
        return styles

    return styler.apply(band, axis=1)


def polish_for_variant(
    data: Any,
    variant: TableVariant,
    *,
    signed_cols: list[str] | None = None,
    auto_signed: bool = True,
) -> Any:
    """realtime: giữ nguyên (caller tự style). analytical/compact: zebra + tô dấu nếu DataFrame thô."""
    if variant == "realtime":
        return data
    frame = unwrap_frame(data)
    if frame is None:
        return data
    cols = list(signed_cols or [])
    if auto_signed and not cols:
        cols = detect_signed_columns([str(c) for c in frame.columns])
    present = [c for c in cols if c in frame.columns]
    # Đã là Styler (desk/overview tự tô) → zebra bỏ cột signed
    if type(data).__name__ == "Styler":
        try:
            return apply_zebra(data, skip_cols=present)
        except Exception:
            return data
    styler = frame.style
    # Zebra trước, signed sau (color/font-weight thắng trên ô Δ)
    try:
        styler = apply_zebra(styler, skip_cols=present)
    except Exception:
        pass
    if present:
        numeric = [c for c in present if pd.api.types.is_numeric_dtype(frame[c])]
        textual = [c for c in present if c not in numeric]
        if numeric:
            styler = styler.map(css_signed_number, subset=numeric)
        if textual:
            styler = styler.map(css_signed_text, subset=textual)
    return styler
