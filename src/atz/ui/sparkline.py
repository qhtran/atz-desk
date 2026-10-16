"""Sparkline dùng chung: SVG (thẻ chỉ số) + cột LineChart (bảng mã)."""

from __future__ import annotations

import html
from typing import Sequence

import streamlit as st

from ui.theme_tokens import DOWN, REF, TEXT_MUTED, UP

GREEN, RED, YELLOW, GREY = UP, DOWN, REF, TEXT_MUTED


def sparkline_svg(
    values: Sequence[float],
    ref: float | None,
    uid: str,
    w: int = 120,
    h: int = 40,
) -> str:
    """SVG: polyline clip trên/dưới vạch tham chiếu vàng; chấm điểm cuối."""
    if not values:
        return (
            f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<line x1="0" y1="{h / 2}" x2="{w}" y2="{h / 2}" stroke="{GREY}" stroke-dasharray="2 3"/></svg>'
        )
    vals = list(values) if len(values) > 1 else list(values) * 2
    ref_v = vals[0] if ref is None else float(ref)
    lo, hi = min(min(vals), ref_v), max(max(vals), ref_v)
    span = (hi - lo) or 1.0
    pad = 3

    def y(v: float) -> float:
        return round(pad + (hi - v) / span * (h - 2 * pad), 2)

    step = (w - 2 * pad) / (len(vals) - 1)
    pts = " ".join(f"{round(pad + i * step, 2)},{y(v)}" for i, v in enumerate(vals))
    ry = y(ref_v)
    lx, ly = round(pad + (len(vals) - 1) * step, 2), y(vals[-1])
    dot = GREEN if vals[-1] > ref_v else RED if vals[-1] < ref_v else YELLOW
    u = html.escape(uid)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs><clipPath id="up-{u}"><rect x="0" y="0" width="{w}" height="{ry}"/></clipPath>'
        f'<clipPath id="dn-{u}"><rect x="0" y="{ry}" width="{w}" height="{h - ry}"/></clipPath></defs>'
        f'<line x1="0" y1="{ry}" x2="{w}" y2="{ry}" stroke="{YELLOW}" stroke-width="1"/>'
        f'<polyline points="{pts}" fill="none" stroke="{GREEN}" stroke-width="1.5" clip-path="url(#up-{u})"/>'
        f'<polyline points="{pts}" fill="none" stroke="{RED}" stroke-width="1.5" clip-path="url(#dn-{u})"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2.5" fill="{dot}"/></svg>'
    )


def line_chart_column(label: str = "Xu hướng", *, width: str = "small", color: str | None = None):
    """column_config cho st.dataframe — ô chứa list[float]."""
    kwargs = {"label": label, "width": width, "help": "Chuỗi giá gần đây (sparkline)"}
    if color:
        kwargs["color"] = color
    return st.column_config.LineChartColumn(**kwargs)


def chart_color_for_change(change: float | None) -> str:
    if change is None or change == 0:
        return YELLOW
    return GREEN if change > 0 else RED
