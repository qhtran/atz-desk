"""Sparkline dùng chung: SVG chỉ số (clip TC) + SVG bảng mã (một màu theo Δ)."""

from __future__ import annotations

import base64
import html
from typing import Sequence

import streamlit as st

from ui.theme_tokens import CEILING, DOWN, FLOOR, REF, TEXT_MUTED, UP, color_for_change

GREEN, RED, YELLOW, GREY = UP, DOWN, REF, TEXT_MUTED


def color_for_price_state(state: str, change: float | None = None) -> str:
    if state == "ceiling":
        return CEILING
    if state == "floor":
        return FLOOR
    return color_for_change(change)


def sparkline_svg(
    values: Sequence[float],
    ref: float | None,
    uid: str,
    w: int = 120,
    h: int = 40,
) -> str:
    """SVG chỉ số: clip trên/dưới vạch tham chiếu vàng (thẻ index)."""
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


def sparkline_trend_svg(
    values: Sequence[float],
    change: float | None,
    uid: str,
    w: int = 100,
    h: int = 28,
    *,
    state: str | None = None,
) -> str:
    """Sparkline bảng mã kiểu FireAnt: cả đường một màu theo Δ / trần / sàn."""
    color = color_for_price_state(state or "", change) if state else color_for_change(change)
    if not values:
        return (
            f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
            f'<line x1="0" y1="{h / 2}" x2="{w}" y2="{h / 2}" stroke="{GREY}" stroke-dasharray="2 3"/></svg>'
        )
    vals = list(values) if len(values) > 1 else list(values) * 2
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 2

    def y(v: float) -> float:
        return round(pad + (hi - v) / span * (h - 2 * pad), 2)

    step = (w - 2 * pad) / (len(vals) - 1)
    pts = " ".join(f"{round(pad + i * step, 2)},{y(v)}" for i, v in enumerate(vals))
    lx, ly = round(pad + (len(vals) - 1) * step, 2), y(vals[-1])
    _ = uid  # giữ chữ ký ổn định nếu sau này cần clip id
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="{lx}" cy="{ly}" r="2.2" fill="{color}"/></svg>'
    )


def svg_data_uri(svg: str) -> str:
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


def spark_image_uri(
    values: Sequence[float],
    change: float | None,
    uid: str,
    *,
    state: str | None = None,
) -> str:
    return svg_data_uri(sparkline_trend_svg(values, change, uid, state=state))


def trend_image_column(label: str = "Xu hướng", *, width: str = "small"):
    return st.column_config.ImageColumn(label, width=width, help="Sparkline theo màu tăng/giảm FireAnt")


def line_chart_column(label: str = "Xu hướng", *, width: str = "small", color: str | None = None):
    """Giữ API cũ; bảng mã nên dùng trend_image_column + spark_image_uri."""
    kwargs = {"label": label, "width": width, "help": "Chuỗi giá gần đây (sparkline)"}
    if color:
        kwargs["color"] = color
    return st.column_config.LineChartColumn(**kwargs)


def chart_color_for_change(change: float | None) -> str:
    return color_for_change(change)
