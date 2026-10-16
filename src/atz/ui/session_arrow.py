"""Mũi tên phiên kiểu mentor/FireAnt: vạch vàng = tham chiếu, thân xanh/đỏ = tăng/giảm."""
from __future__ import annotations

import base64
from xml.sax.saxutils import escape

from ui.theme_tokens import DOWN, REF, TEXT_MUTED, UP


def _y(price: float, lo: float, hi: float, top: float, bottom: float) -> float:
    span = (hi - lo) or 1.0
    return round(top + (hi - price) / span * (bottom - top), 2)


def session_arrow_svg(
    ref: float,
    high: float,
    low: float,
    close: float,
    *,
    width: int = 72,
    height: int = 36,
) -> str:
    """SVG: đường ngang vàng (ref), range cao→thấp, mũi tên kết thúc ở giá đóng."""
    hi = max(high, low, close, ref)
    lo = min(high, low, close, ref)
    pad_x, pad_y = 6, 4
    top, bottom = pad_y, height - pad_y
    color = UP if close > ref else DOWN if close < ref else REF
    y_ref = _y(ref, lo, hi, top, bottom)
    y_hi = _y(high, lo, hi, top, bottom)
    y_lo = _y(low, lo, hi, top, bottom)
    y_close = _y(close, lo, hi, top, bottom)
    x0, x1, x2 = pad_x, width * 0.45, width - pad_x - 2
    # Thân: cao → thấp → đóng cửa
    pts = f"{x0},{y_hi} {x1},{y_lo} {x2},{y_close}"
    # Đầu mũi tên hướng theo đoạn cuối (thấp → đóng)
    tip = 5
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<line x1="0" y1="{y_ref}" x2="{width}" y2="{y_ref}" '
        f'stroke="{REF}" stroke-width="1.2"/>'
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<polygon points="{x2},{y_close} {x2 - tip},{y_close - tip * 0.6} '
        f'{x2 - tip},{y_close + tip * 0.6}" fill="{color}"/>'
        f"</svg>"
    )
    return svg


def session_arrow_data_uri(ref: float, high: float, low: float, close: float) -> str:
    svg = session_arrow_svg(ref, high, low, close)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def session_arrow_or_dash(
    ref: float | None,
    high: float | None,
    low: float | None,
    close: float | None,
) -> str:
    """Giá trị ô cột mũi tên: data-URI hoặc placeholder xám."""
    if None in (ref, high, low, close):
        # SVG trống có vạch xám — ImageColumn vẫn hiện ô
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="72" height="36">'
            f'<line x1="8" y1="18" x2="64" y2="18" stroke="{escape(TEXT_MUTED)}" '
            f'stroke-dasharray="3 3"/></svg>'
        )
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    return session_arrow_data_uri(float(ref), float(high), float(low), float(close))
