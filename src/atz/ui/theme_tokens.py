"""Màu UI chuẩn FireAnt / chứng khoán VN (tăng–giảm–tham chiếu–trần–sàn).

Nguồn hex: phân tích FireAnt (scan UI) + token app.
Không hardcode hex ở từng trang — import từ đây.
"""
from __future__ import annotations

# --- Nền ---
BG_PRIMARY = "#121418"
BG_CARD = "#1E232A"

# --- Price action (FireAnt) ---
UP = "#00C853"  # tăng / lãi / sparkline tăng
DOWN = "#FF3D00"  # giảm / lỗ / sparkline giảm
REF = "#FFC107"  # tham chiếu / đứng giá / nền cột giá mua
CEILING = "#AB47BC"  # giá trần (tím VN)
FLOOR = "#29B6F6"  # giá sàn (xanh dương VN)

# --- Chữ ---
TEXT_PRIMARY = "#FFFFFF"
TEXT_MUTED = "#9E9E9E"
TEXT_DARK = "#212121"  # chữ trên nền sáng / nền vàng giá mua


def css_up() -> str:
    return f"color: {UP}"


def css_down() -> str:
    return f"color: {DOWN}"


def css_ref() -> str:
    return f"color: {REF}"


def css_ceiling() -> str:
    return f"color: {CEILING}; font-weight: 700"


def css_floor() -> str:
    return f"color: {FLOOR}; font-weight: 700"


def css_for_price_state(state: str) -> str:
    """Map price_action.price_state → CSS chữ."""
    if state == "ceiling":
        return css_ceiling()
    if state == "floor":
        return css_floor()
    if state == "up":
        return css_up()
    if state == "down":
        return css_down()
    if state == "flat":
        return css_ref()
    return ""


def css_buy_column() -> str:
    """Cột Giá mua: nền vàng tham chiếu, chữ tối dễ đọc."""
    return f"background-color: {REF}; color: {TEXT_DARK}; font-weight: 600"


def css_support() -> str:
    return css_down()


def css_resist() -> str:
    return css_up()


def css_signed_number(value: object) -> str:
    """Tô màu theo dấu số. 0 = vàng tham chiếu."""
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


def color_for_change(change: float | None) -> str:
    """Màu sparkline / chữ theo biến động phiên."""
    if change is None:
        return TEXT_MUTED
    try:
        number = float(change)
    except (TypeError, ValueError):
        return TEXT_MUTED
    if number > 0:
        return UP
    if number < 0:
        return DOWN
    return REF


FIREANT_CSS = f"""
<style>
.text-green {{ color: {UP} !important; }}
.text-red {{ color: {DOWN} !important; }}
.text-ref {{ color: {REF} !important; }}
.text-ceiling {{ color: {CEILING} !important; }}
.text-floor {{ color: {FLOOR} !important; }}
.text-muted {{ color: {TEXT_MUTED} !important; }}
@keyframes fa-flash-up {{
  0% {{ background-color: {UP}66; }}
  100% {{ background-color: transparent; }}
}}
@keyframes fa-flash-dn {{
  0% {{ background-color: {DOWN}66; }}
  100% {{ background-color: transparent; }}
}}
</style>
"""


def css_flash(up: bool) -> str:
    """Nháy nền ô giá khi vừa đổi (Realtime fragment)."""
    name = "fa-flash-up" if up else "fa-flash-dn"
    return f"animation: {name} 0.85s ease-out"
