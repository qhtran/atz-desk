"""Màu UI kiểu FireAnt / chuẩn chứng khoán (tăng–giảm–tham chiếu).

Dùng chung cho bảng vị thế, Tổng quan, Realtime, thẻ chỉ số.
Không hardcode hex ở từng trang — import từ đây.
"""
from __future__ import annotations

# --- Nền ---
BG_PRIMARY = "#121418"
BG_CARD = "#1E232A"

# --- Trạng thái số liệu ---
UP = "#00C087"  # tăng / lãi / tích cực
DOWN = "#E53935"  # giảm / lỗ / tiêu cực
REF = "#FFC107"  # tham chiếu / không đổi / highlight giá mua
CEILING = "#9C27B0"  # giá trần (tím) — dự phòng
FLOOR = "#00BCD4"  # giá sàn / khối ngoại (cyan) — dự phòng

# --- Chữ ---
TEXT_PRIMARY = "#E0E0E0"
TEXT_MUTED = "#848E9C"


def css_up() -> str:
    return f"color: {UP}"


def css_down() -> str:
    return f"color: {DOWN}"


def css_ref() -> str:
    return f"color: {REF}"


def css_buy_column() -> str:
    """Cột Giá mua: nền vàng tham chiếu, chữ tối dễ đọc."""
    return f"background-color: {REF}; color: #1a1a1a; font-weight: 600"


def css_support() -> str:
    return css_down()


def css_resist() -> str:
    return css_up()


def css_signed_number(value: object) -> str:
    """Tô màu theo dấu số (Realtime / Top 20). 0 = vàng tham chiếu."""
    try:
        if value is None or (isinstance(value, float) and value != value):
            return ""
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if number > 0:
        return css_up()
    if number < 0:
        return css_down()
    return css_ref()


def css_signed_text(value: object) -> str:
    """Tô màu chuỗi đã format (+1.2%, ▲, ▼) hoặc nhãn Tăng/Giảm."""
    text = str(value).strip()
    if text.startswith("+") or text in {"▲", "Tăng"}:
        return css_up()
    if text.startswith("-") or text in {"▼", "Giảm"}:
        return css_down()
    return ""
