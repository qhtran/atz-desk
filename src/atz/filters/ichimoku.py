"""Ichimoku: giá so với mây và Tenkan cắt Kijun. Công thức ở analysis.technical."""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import ichimoku
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="ichimoku",
    label="Ichimoku",
    description="Giá đóng cửa ra khỏi mây và Tenkan cắt Kijun ở phiên cuối.",
    group="xu hướng",
    params=(
        ParamSpec("tenkan", "int", C.ICHIMOKU_TENKAN, "Tenkan", min=2, max=30),
        ParamSpec("kijun", "int", C.ICHIMOKU_KIJUN, "Kijun", min=3, max=60),
        ParamSpec("senkou_b", "int", C.ICHIMOKU_SENKOU_B, "Senkou B", min=4, max=120),
        ParamSpec("displacement", "int", C.ICHIMOKU_DISPLACEMENT, "Dịch mây", min=1, max=60),
    ),
)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    tenkan_n, kijun_n = chosen["tenkan"], chosen["kijun"]
    span_n, shift = chosen["senkou_b"], chosen["displacement"]
    if not tenkan_n < kijun_n <= span_n:
        return waiting("Tenkan < Kijun <= Senkou B")
    high = pd.to_numeric(bars["high"], errors="coerce")
    low = pd.to_numeric(bars["low"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    tenkan, kijun, cloud_a, cloud_b = ichimoku(high, low, tenkan_n, kijun_n, span_n, shift)
    if len(close) < 2 or cloud_a.iloc[-1:].isna().any() or cloud_b.iloc[-1:].isna().any():
        return waiting()
    if tenkan.iloc[-2:].isna().any() or kijun.iloc[-2:].isna().any() or pd.isna(close.iloc[-1]):
        return waiting()
    price = float(close.iloc[-1])
    upper = max(float(cloud_a.iloc[-1]), float(cloud_b.iloc[-1]))
    lower = min(float(cloud_a.iloc[-1]), float(cloud_b.iloc[-1]))
    tk, kj = float(tenkan.iloc[-1]), float(kijun.iloc[-1])
    prev_tk, prev_kj = float(tenkan.iloc[-2]), float(kijun.iloc[-2])
    details = {
        "close": round(price, 4),
        "tenkan": round(tk, 4),
        "kijun": round(kj, 4),
        "cloud_high": round(upper, 4),
        "cloud_low": round(lower, 4),
    }
    cross_up = prev_tk <= prev_kj and tk > kj
    cross_down = prev_tk >= prev_kj and tk < kj
    above = price > upper
    below = price < lower
    if above and cross_up:
        return hit("mua", "Giá trên mây và Tenkan cắt lên Kijun", details)
    if below and cross_down:
        return hit("ban", "Giá dưới mây và Tenkan cắt xuống Kijun", details)
    if cross_up:
        return hold("Tenkan cắt lên nhưng giá chưa trên mây", details)
    if cross_down:
        return hold("Tenkan cắt xuống nhưng giá chưa dưới mây", details)
    if above:
        return hold("Giá trên mây, Tenkan chưa cắt", details)
    if below:
        return hold("Giá dưới mây, Tenkan chưa cắt", details)
    return hold("Giá trong mây", details)
