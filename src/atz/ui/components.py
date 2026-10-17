"""Thành phần UI dùng chung: bảng 3 variants + biểu đồ chiều cao cố định."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import streamlit as st

from ui.mobile import pinned
from ui.table_theme import (
    TableVariant,
    container_key,
    inject_table_theme,
    normalize_variant,
    polish_for_variant,
    unwrap_frame,
)

CHART_MIN_HEIGHT = 400
CHART_MAX_HEIGHT = 450
CHART_DEFAULT_HEIGHT = 420


def _columns_of(data: Any) -> list[str]:
    frame = unwrap_frame(data)
    if frame is not None:
        return [str(c) for c in frame.columns]
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return [str(c) for c in data[0]]
    return []


def render_data_table(
    data: Any,
    pin: Sequence[str] | str | None = None,
    key_cols: Sequence[str] | None = None,
    *,
    variant: TableVariant | str = "analytical",
    key: str | None = None,
    dbg_key: str | None = None,
    glance_label: str = "Chỉ hiện cột chính",
    column_config: dict | None = None,
    signed_cols: Sequence[str] | None = None,
    auto_signed: bool = True,
    **kwargs: Any,
) -> None:
    """Một helper bảng — 3 variants: ``realtime`` | ``analytical`` | ``compact``.

    - ``realtime``: bảng giá (flash/spark do caller); mật độ siêu dày.
    - ``analytical``: Tổng quan / desk / watchlist / filter — pin cột, zebra, tô Δ/PnL.
    - ``compact``: sidebar / khối ghim / alerts — thu nhỏ.

    Có ``key_cols`` thì thêm toggle Glance. ``dbg_key``/``key`` → chip debug.
    """
    inject_table_theme()
    kind = normalize_variant(variant)
    columns = _columns_of(data)
    if pin is None:
        if "Mã" in columns:
            pins = ["Mã"]
        elif columns:
            pins = [columns[0]] if kind == "compact" else []
        else:
            pins = []
    else:
        pins = [pin] if isinstance(pin, str) else list(pin or [])
        pins = [name for name in pins if name in columns] if columns else pins
    config = dict(pinned(*pins))
    if column_config:
        config.update(column_config)
    order = None
    if key_cols and columns and kind != "compact":
        wanted = [c for c in [*pins, *key_cols] if c in columns]
        if wanted and len(wanted) < len(columns):
            glance = st.toggle(glance_label, value=False, key=f"glance_{key}" if key else None)
            if glance:
                order = list(dict.fromkeys(wanted))
    table_dbg = dbg_key or key
    if table_dbg:
        from ui.debug_overlay import dbg_table_legend

        visible_cols = order if order else columns
        dbg_table_legend(str(table_dbg), visible_cols, data=data)
    display = polish_for_variant(
        data,
        kind,
        signed_cols=list(signed_cols) if signed_cols else None,
        auto_signed=auto_signed and kind != "realtime",
    )
    kwargs.setdefault("hide_index", True)
    if kind == "compact":
        kwargs.setdefault("height", 280)
    wrap = container_key(kind, key)
    with st.container(key=wrap, border=(kind == "compact")):
        st.dataframe(
            display,
            width="stretch",
            column_config=config or None,
            column_order=order,
            key=key,
            **kwargs,
        )


MOBILE_CHART_HEIGHT = 420
_TICK_COUNT = 6


def _date_ticks(fig: Any, count: int) -> None:
    """Trục ngày dạng category 'YYYY-MM-DD': chọn ~count mốc, hiện dd/mm, không xoay."""
    xs: list[str] = []
    for trace in fig.data:
        values = getattr(trace, "x", None)
        if values is not None and len(values) > len(xs):
            xs = [str(v) for v in values]
    if len(xs) < 2 or not (len(xs[0]) == 10 and xs[0][4] == "-" and xs[0][7] == "-"):
        fig.update_xaxes(nticks=count, tickangle=0)
        return
    step = max(1, (len(xs) - 1) // (count - 1))
    picks = list(range(0, len(xs), step))[:count]
    if picks[-1] != len(xs) - 1 and len(xs) - 1 - picks[-1] > step // 2:
        picks[-1] = len(xs) - 1
    vals = [xs[i] for i in picks]
    fig.update_xaxes(tickmode="array", tickvals=vals, ticktext=[f"{v[8:10]}/{v[5:7]}" for v in vals], tickangle=0)


def render_chart(fig: Any, height: int | None = None, *, key: str | None = None, **kwargs: Any) -> None:
    """Plotly: bản desktop giữ chiều cao/chú thích gốc; bản mobile cao cố định 420px, chú thích dưới.

    CSS trong ui/mobile.py chỉ hiện một bản theo media query, nên không méo khi co giãn.
    """
    module = type(fig).__module__
    if not module.startswith("plotly"):
        if module.startswith("altair"):
            st.altair_chart(fig.properties(height=height or CHART_DEFAULT_HEIGHT), width="stretch", **kwargs)
        else:
            st.line_chart(fig, height=height or CHART_DEFAULT_HEIGHT, width="stretch", **kwargs)
        return
    import copy

    title = getattr(getattr(fig.layout, "title", None), "text", "") or ""
    ident = key or f"{abs(hash(title)) % 10**8}_{height or fig.layout.height or 0}"
    kwargs.setdefault("theme", None)
    config = {"responsive": True, "displaylogo": False}

    desktop = copy.deepcopy(fig)
    if height:
        desktop.update_layout(height=int(height))
    _date_ticks(desktop, _TICK_COUNT)
    with st.container(key=f"dschart-d-{ident}"):
        st.plotly_chart(desktop, width="stretch", config=config, key=f"pd_{ident}", **kwargs)

    mobile = copy.deepcopy(fig)
    mobile.update_layout(
        height=MOBILE_CHART_HEIGHT,
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, font=dict(size=10)),
        margin=dict(l=36, r=8, t=44, b=70),
        title=dict(font=dict(size=13)),
    )
    _date_ticks(mobile, 5)
    with st.container(key=f"dschart-m-{ident}"):
        st.plotly_chart(mobile, width="stretch", config=config, key=f"pm_{ident}", **kwargs)
