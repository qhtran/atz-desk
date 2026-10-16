"""Khối lượng mua theo khoảng cách cắt lỗ. Không vẽ giao diện."""

from __future__ import annotations

import math

import pandas as pd

from config import THOUSAND_VND
from khuyen_nghi import PORTFOLIO


def recommendation_stop(symbol: str) -> float | None:
    matched = PORTFOLIO.loc[PORTFOLIO["Mã CK"].astype(str).str.upper() == symbol, "Giá cắt lỗ động"]
    if matched.empty:
        return None
    value = pd.to_numeric(matched.iloc[0], errors="coerce")
    if pd.isna(value):
        return None
    return float(value)


def position_plan(
    price: float, stop: float, capital: float, risk_pct: float
) -> dict[str, float] | str:
    """Số cổ phiếu theo rủi ro. Giá bằng cắt lỗ thì không chia."""
    if price <= 0 or capital < 0 or risk_pct < 0:
        return "Giá hoặc vốn không hợp lệ."
    if price <= stop:
        return "Giá đã chạm hoặc thủng cắt lỗ. Không tính khối lượng mua."
    gap_vnd = round((price - stop) * THOUSAND_VND)
    if gap_vnd <= 0:
        return "Khoảng cách cắt lỗ không đủ để chia."
    max_loss = capital * (risk_pct / 100)
    shares = math.floor(max_loss / gap_vnd)
    return {
        "distance_pct": (price - stop) / price * 100,
        "max_loss": max_loss,
        "shares": float(shares),
        "gap_vnd": gap_vnd,
    }
