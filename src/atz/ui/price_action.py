"""Trạng thái giá phiên VN: tăng/giảm/đứng + trần/sàn.

Ưu tiên ceiling/floor thật từ quote (price_board). Thiếu thì ước lượng từ TC:
HOSE ±7%, HNX ±10%, UPCOM ±15% (config BAND_*).
"""

from __future__ import annotations

from config import BAND_HNX, BAND_HOSE, BAND_UPCOM


def band_pct(exchange: str | None) -> float:
    text = str(exchange or "").upper()
    if "UP" in text or "UPCOM" in text:
        return float(BAND_UPCOM)
    if "HNX" in text or "HN" == text:
        return float(BAND_HNX)
    return float(BAND_HOSE)


def limit_prices(ref: float, exchange: str | None = None) -> tuple[float, float]:
    """(ceiling, floor) từ giá tham chiếu."""
    pct = band_pct(exchange)
    return ref * (1.0 + pct), ref * (1.0 - pct)


def price_state(
    price: float | None,
    ref: float | None,
    *,
    exchange: str | None = None,
    ceiling: float | None = None,
    floor: float | None = None,
) -> str:
    """ceiling | floor | up | down | flat | unknown."""
    if price is None or ref is None:
        return "unknown"
    try:
        px, tc = float(price), float(ref)
    except (TypeError, ValueError):
        return "unknown"
    if tc <= 0:
        return "unknown"
    ceil = float(ceiling) if ceiling is not None else limit_prices(tc, exchange)[0]
    flr = float(floor) if floor is not None else limit_prices(tc, exchange)[1]
    tol = max(tc * 0.0005, 1.0)
    if px >= ceil - tol:
        return "ceiling"
    if px <= flr + tol:
        return "floor"
    if px > tc:
        return "up"
    if px < tc:
        return "down"
    return "flat"
