"""Nhận diện mẫu hình giá (HEURISTIC). Chỉ là gợi ý từ quy tắc đơn giản trên OHLCV ngày,
không thay thế việc nhìn đồ thị. Mỗi hàm trả dict: name, found (bool), detail (str)."""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
from analysis.technical import sma

P = C.PATTERNS


def _pivots(values: np.ndarray, order: int, kind: str) -> list[int]:
    """Chỉ số các cực tiểu (kind='low') hoặc cực đại ('high') cục bộ trong ±order phiên."""
    out = []
    for i in range(order, len(values) - order):
        window = values[i - order : i + order + 1]
        if kind == "low" and values[i] == window.min():
            out.append(i)
        if kind == "high" and values[i] == window.max():
            out.append(i)
    return out


def uptrend(w: pd.DataFrame) -> dict:
    close = w["close"].astype(float)
    ma20, ma50 = sma(close, C.MA_SHORT), sma(close, C.MA_MID)
    ma150 = sma(close, C.MA_LONG)
    name = "Xu hướng tăng"
    if ma50.dropna().shape[0] < 10:
        return {"name": name, "found": False, "detail": "Chưa đủ phiên tính MA50."}
    price = close.iloc[-1]
    rising = ma50.iloc[-1] > ma50.iloc[-10]
    aligned = price > ma20.iloc[-1] > ma50.iloc[-1]
    long_ok = pd.isna(ma150.iloc[-1]) or ma50.iloc[-1] > ma150.iloc[-1]
    found = bool(aligned and rising and long_ok)
    detail = (f"Giá {price:.2f}, MA20 {ma20.iloc[-1]:.2f}, MA50 {ma50.iloc[-1]:.2f}"
              + ("" if pd.isna(ma150.iloc[-1]) else f", MA150 {ma150.iloc[-1]:.2f}")
              + f"; MA50 {'dốc lên' if rising else 'không dốc lên'} trong 10 phiên.")
    return {"name": name, "found": found, "detail": detail}


def flat_base(w: pd.DataFrame) -> dict:
    name = "Nền phẳng"
    n = P["FLAT_BASE_BARS"]
    if len(w) < n + 20:
        return {"name": name, "found": False, "detail": "Chưa đủ phiên."}
    seg = w.tail(n)
    hi, lo = float(seg["high"].max()), float(seg["low"].min())
    width = hi / lo - 1 if lo > 0 else 1.0
    prior = w["close"].iloc[-(n + 60):-n].astype(float)
    advanced = len(prior) > 0 and lo > float(prior.min()) * 1.15  # nền hình thành sau một nhịp tăng
    found = bool(width <= P["FLAT_BASE_MAX_RANGE"] and advanced)
    detail = f"{n} phiên gần nhất dao động {width * 100:.1f}% ({lo:.2f}–{hi:.2f})" + (
        "; có nhịp tăng ≥15% trước nền." if advanced else "; chưa thấy nhịp tăng trước nền.")
    return {"name": name, "found": found, "detail": detail}


def triple_bottom(w: pd.DataFrame) -> dict:
    name = "Ba đáy"
    seg = w.tail(P["TRIPLE_BOTTOM_BARS"]).reset_index(drop=True)
    lows = seg["low"].astype(float).to_numpy()
    piv = _pivots(lows, P["PIVOT_ORDER"], "low")
    if len(piv) < 3:
        return {"name": name, "found": False, "detail": "Chưa đủ 3 đáy cục bộ."}
    floor = lows.min()
    near = [i for i in piv if lows[i] <= floor * (1 + P["TRIPLE_BOTTOM_TOL"])]
    # gộp các đáy quá sát nhau (< 2*order phiên) thành một
    picked: list[int] = []
    for i in near:
        if not picked or i - picked[-1] >= 2 * P["PIVOT_ORDER"]:
            picked.append(i)
    if len(picked) < 3:
        return {"name": name, "found": False,
                "detail": f"Có {len(picked)} lần chạm vùng đáy {floor:.2f} (cần 3)."}
    a, c = picked[-3], picked[-1]
    neckline = float(seg["high"].iloc[a:c + 1].max())
    price = float(seg["close"].iloc[-1])
    detail = (f"3 đáy quanh {floor:.2f} (sai lệch ≤{P['TRIPLE_BOTTOM_TOL'] * 100:.0f}%), "
              f"đường cổ {neckline:.2f}; giá {'đã vượt' if price > neckline else 'chưa vượt'} đường cổ.")
    return {"name": name, "found": True, "detail": detail}


def cup_with_handle(w: pd.DataFrame) -> dict:
    name = "Cốc tay cầm"
    close = w["close"].astype(float).reset_index(drop=True)
    n = len(close)
    if n < P["CUP_MIN_BARS"] + 5:
        return {"name": name, "found": False, "detail": "Chưa đủ phiên."}
    highs = close.to_numpy()
    piv = _pivots(highs, P["PIVOT_ORDER"], "high")
    best = None
    # Miệng phải: đỉnh cục bộ trong HANDLE_MAX_BARS phiên cuối; miệng trái: đỉnh trước đó.
    for right in reversed(piv):
        if n - 1 - right > P["HANDLE_MAX_BARS"]:
            break
        for left in reversed([p for p in piv if p < right]):
            span = right - left
            if span < P["CUP_MIN_BARS"]:
                continue
            if span > P["CUP_MAX_BARS"]:
                break
            lrim, rrim = highs[left], highs[right]
            bottom = highs[left:right + 1].min()
            depth = 1 - bottom / max(lrim, rrim)
            if not (P["CUP_DEPTH_MIN"] <= depth <= P["CUP_DEPTH_MAX"]):
                continue
            if abs(rrim / lrim - 1) > P["CUP_RIM_TOL"]:
                continue
            # đáy cốc nằm ở khúc giữa (hình chữ U, không lệch hẳn một bên)
            pos = (int(np.argmin(highs[left:right + 1]))) / span
            if not 0.25 <= pos <= 0.75:
                continue
            handle = highs[right:]
            h_depth = 1 - handle.min() / rrim if len(handle) > 1 else 0.0
            if h_depth > P["HANDLE_MAX_DEPTH"] or handle.min() < bottom + (rrim - bottom) / 2:
                continue
            best = (left, right, depth, h_depth, rrim)
            break
        if best:
            break
    if not best:
        return {"name": name, "found": False, "detail": "Không thấy cốc 12–40% với tay cầm nông."}
    left, right, depth, h_depth, rim = best
    detail = (f"Cốc dài {right - left} phiên, sâu {depth * 100:.0f}%, tay cầm sâu {h_depth * 100:.0f}% "
              f"trong {n - 1 - right} phiên; điểm mua tham khảo khi vượt {rim:.2f}.")
    return {"name": name, "found": True, "detail": detail}


DETECTORS = [uptrend, flat_base, triple_bottom, cup_with_handle]


def detect_all(w: pd.DataFrame) -> list[dict]:
    results = []
    for fn in DETECTORS:
        try:
            results.append(fn(w))
        except Exception as error:  # một detector lỗi không làm hỏng trang
            results.append({"name": fn.__name__, "found": False, "detail": f"Lỗi: {error}"})
    return results
