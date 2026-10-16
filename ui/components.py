"""Thành phần UI dùng chung: bảng ghim cột đầu và biểu đồ chiều cao cố định."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
import streamlit as st

from ui.mobile import pinned

CHART_MIN_HEIGHT = 400
CHART_MAX_HEIGHT = 450
CHART_DEFAULT_HEIGHT = 420


def _columns_of(data: Any) -> list[str]:
    frame = getattr(data, "data", data)  # Styler giữ DataFrame trong .data
    if isinstance(frame, pd.DataFrame):
        return [str(c) for c in frame.columns]
    if isinstance(frame, list) and frame and isinstance(frame[0], dict):
        return [str(c) for c in frame[0]]
    return []


def render_data_table(
    data: Any,
    pin: Sequence[str] | str | None = ("Mã",),
    key_cols: Sequence[str] | None = None,
    *,
    key: str | None = None,
    glance_label: str = "Chỉ hiện cột chính",
    column_config: dict | None = None,
    **kwargs: Any,
) -> None:
    """st.dataframe full width, ghim cột đầu.

    Mặc định hiện mọi cột (desktop như cũ). Có ``key_cols`` thì thêm toggle Glance để
    chỉ xem cột chính, hữu ích trên điện thoại.
    """
    columns = _columns_of(data)
    pins = [pin] if isinstance(pin, str) else list(pin or [])
    pins = [name for name in pins if name in columns] if columns else pins
    config = dict(pinned(*pins))
    if column_config:
        config.update(column_config)
    order = None
    if key_cols and columns:
        wanted = [c for c in [*pins, *key_cols] if c in columns]
        if wanted and len(wanted) < len(columns):
            glance = st.toggle(glance_label, value=False, key=f"glance_{key}" if key else None)
            if glance:
                order = list(dict.fromkeys(wanted))
    kwargs.setdefault("hide_index", True)
    st.dataframe(
        data,
        width="stretch",
        column_config=config or None,
        column_order=order,
        key=key,
        **kwargs,
    )


def render_chart(fig: Any, height: int = CHART_DEFAULT_HEIGHT, **kwargs: Any) -> None:
    """Biểu đồ full width, chiều cao cố định 400–450px để không méo trên điện thoại."""
    height = max(CHART_MIN_HEIGHT, min(CHART_MAX_HEIGHT, int(height)))
    module = type(fig).__module__
    if module.startswith("plotly"):
        fig.update_layout(height=height, autosize=True)
        kwargs.setdefault("theme", None)
        st.plotly_chart(fig, width="stretch", config={"responsive": True, "displaylogo": False}, **kwargs)
        return
    if module.startswith("altair"):
        st.altair_chart(fig.properties(height=height), width="stretch", **kwargs)
        return
    st.line_chart(fig, height=height, width="stretch", **kwargs)
