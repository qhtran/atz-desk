"""RSI Wilder qua analysis.technical.rsi.

mode "f1" (mặc định, F1 mục 7 hàng 2): mua khi RSI có >= min_bottoms đáy trong vùng
oversold + bottom_band rồi vượt "đáy trung tâm" RSI (analysis.technical.rsi_bottoms).
mode "co_ban": RSI phiên cuối dưới vùng bán / trên vùng mua như trước.
"""

from __future__ import annotations

import pandas as pd

import config as C
from analysis.technical import rsi, rsi_bottoms
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

FILTER = FilterSpec(
    name="rsi",
    label="RSI",
    description="F1: 2–3 đáy RSI vùng ~30 rồi vượt đáy trung tâm. Cơ bản: RSI dưới vùng bán / trên vùng mua.",
    group="dao động",
    params=(
        ParamSpec("mode", "choice", "f1", "Chế độ", choices=("f1", "co_ban")),
        ParamSpec("length", "int", C.RSI_LENGTH, "Số phiên", min=2, max=100),
        ParamSpec("oversold", "float", float(C.RSI_OVERSOLD), "Ngưỡng mua", min=1, max=50),
        ParamSpec("overbought", "float", float(C.RSI_OVERBOUGHT), "Ngưỡng bán", min=50, max=99),
        ParamSpec("bottom_band", "float", 5.0, "F1: biên vùng đáy (+ điểm)", min=0, max=20),
        ParamSpec("min_bottoms", "int", 2, "F1: số đáy tối thiểu", min=2, max=3),
        ParamSpec("lookback", "int", 60, "F1: số phiên tìm đáy", min=20, max=250),
    ),
)

_ORDER = 3  # đáy RSI = thấp nhất trong ±3 phiên


def _f1(series: pd.Series, chosen: dict) -> SignalResult:
    zone = chosen["oversold"] + chosen["bottom_band"]
    scan = rsi_bottoms(series, zone, _ORDER, chosen["lookback"])
    details = {
        "rsi": scan["last"],
        "length": chosen["length"],
        "zone": zone,
        "bottoms": scan["bottoms"],
        "bottom_values": scan["bottom_values"],
        "neckline": scan["neckline"],
    }
    if scan["bottoms"] < chosen["min_bottoms"]:
        return hold(f"RSI mới có {scan['bottoms']} đáy vùng ≤{zone:g} (cần {chosen['min_bottoms']})", details)
    if scan["crossed"]:
        return hit("mua", f"RSI {scan['bottoms']} đáy vùng ≤{zone:g}, vượt đáy trung tâm {scan['neckline']}", details)
    return hold(f"RSI {scan['bottoms']} đáy, chưa vượt đáy trung tâm {scan['neckline']}", details)


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    if "close" not in bars.columns:
        return waiting("không đủ dữ liệu: thiếu cột close")
    close = pd.to_numeric(bars["close"], errors="coerce")
    series = rsi(close, chosen["length"])
    if len(close) <= chosen["length"] or series.empty or pd.isna(series.iloc[-1]):
        return waiting()
    if chosen["mode"] == "f1":
        need = chosen["length"] + 2 * _ORDER + 2
        if series.notna().sum() < 2 * _ORDER + 2:
            return waiting(f"không đủ dữ liệu: F1 cần ≥ {need} phiên")
        return _f1(series, chosen)
    value = series.iloc[-1]
    details = {"rsi": round(float(value), 2), "length": chosen["length"]}
    if value <= chosen["oversold"]:
        return hit("mua", f"RSI {details['rsi']} dưới {chosen['oversold']}", details)
    if value >= chosen["overbought"]:
        return hit("ban", f"RSI {details['rsi']} trên {chosen['overbought']}", details)
    return hold(f"RSI {details['rsi']}", details)
