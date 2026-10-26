"""Chỉ báo kỹ thuật thuần pandas (không gọi mạng). Đầu vào: DataFrame có open/high/low/close/volume."""

from __future__ import annotations

import pandas as pd

import config as C


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def bollinger(close: pd.Series, length: int = C.BB_LENGTH, k: float = C.BB_STD):
    mid = sma(close, length)
    sigma = close.rolling(length, min_periods=length).std(ddof=0)
    return mid - k * sigma, mid, mid + k * sigma




def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _wilder_smooth(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""
    return _wilder_smooth(_true_range(high, low, close), length)


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX, +DI, -DI (Wilder)."""
    tr = _true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_s = _wilder_smooth(tr, length)
    plus_di = 100 * _wilder_smooth(plus_dm, length) / atr_s
    minus_di = 100 * _wilder_smooth(minus_dm, length) / atr_s
    denom = plus_di + minus_di
    dx = (plus_di - minus_di).abs() / denom * 100
    dx = dx.where(denom != 0)
    adx_line = _wilder_smooth(dx, length)
    return adx_line, plus_di, minus_di


def rsi(close: pd.Series, length: int = C.RSI_LENGTH) -> pd.Series:
    """RSI kiểu Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())


def macd(close: pd.Series, fast=C.MACD_FAST, slow=C.MACD_SLOW, signal=C.MACD_SIGNAL):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def _donchian_mid(high: pd.Series, low: pd.Series, length: int) -> pd.Series:
    highest = high.rolling(length, min_periods=length).max()
    lowest = low.rolling(length, min_periods=length).min()
    return (highest + lowest) / 2


def ichimoku(
    high: pd.Series,
    low: pd.Series,
    tenkan: int = C.ICHIMOKU_TENKAN,
    kijun: int = C.ICHIMOKU_KIJUN,
    senkou_b: int = C.ICHIMOKU_SENKOU_B,
    displacement: int = C.ICHIMOKU_DISPLACEMENT,
):
    """Tenkan, Kijun, và mây Senkou A/B đã dịch tới phiên hiện tại.

    Senkou Span A/B tính xong rồi shift `displacement` phiên. Giá trị tại
    phiên cuối chính là mây đang treo trên giá, không phải span vừa tính.
    """
    tenkan_sen = _donchian_mid(high, low, tenkan)
    kijun_sen = _donchian_mid(high, low, kijun)
    span_a = (tenkan_sen + kijun_sen) / 2
    span_b = _donchian_mid(high, low, senkou_b)
    return tenkan_sen, kijun_sen, span_a.shift(displacement), span_b.shift(displacement)


def mcdx(
    close: pd.Series,
    banker_period: int = C.MCDX_BANKER_PERIOD,
    banker_base: float = C.MCDX_BANKER_BASE,
    banker_sens: float = C.MCDX_BANKER_SENS,
    hot_period: int = C.MCDX_HOT_PERIOD,
    hot_base: float = C.MCDX_HOT_BASE,
    hot_sens: float = C.MCDX_HOT_SENS,
):
    """Banker, Hot Money (thang 0–20) và Banker chưa kẹp.

    Banker = sensitivity × (RSI(period) − base), kẹp [0, 20].
    Bản chưa kẹp dùng để bắt cắt qua 0: RSI cắt lên base là sức mạnh tăng.
    """
    banker_raw = banker_sens * (rsi(close, banker_period) - banker_base)
    hot_raw = hot_sens * (rsi(close, hot_period) - hot_base)
    banker = banker_raw.clip(lower=0, upper=20)
    hot = hot_raw.clip(lower=0, upper=20)
    return banker, hot, banker_raw


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = close.diff().apply(lambda d: 1 if d > 0 else (-1 if d < 0 else 0))
    return (direction * volume).cumsum()


def mfi(high, low, close, volume, length: int = C.MFI_LENGTH) -> pd.Series:
    typical = (high + low + close) / 3
    flow = typical * volume
    up = flow.where(typical > typical.shift(), 0.0)
    down = flow.where(typical < typical.shift(), 0.0)
    pos = up.rolling(length, min_periods=length).sum()
    neg = down.rolling(length, min_periods=length).sum()
    ratio = pos / neg
    return (100 - 100 / (1 + ratio)).where(neg != 0, 100.0).where(pos.notna())




def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_length: int = 14,
    d_length: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """%K và %D (SMA của %K)."""
    lowest = low.rolling(k_length, min_periods=k_length).min()
    highest = high.rolling(k_length, min_periods=k_length).max()
    span = highest - lowest
    k_line = 100 * (close - lowest) / span
    k_line = k_line.where(span != 0)
    d_line = k_line.rolling(d_length, min_periods=d_length).mean()
    return k_line, d_line


def rs_vs_index(
    stock: pd.DataFrame,
    index: pd.DataFrame,
    lookback: int = 60,
) -> float | None:
    """Chênh lệch % tăng cổ phiếu trừ index trên lookback phiên (cùng cột time)."""
    if stock is None or index is None or stock.empty or index.empty:
        return None
    s = stock[["time", "close"]].copy()
    i = index[["time", "close"]].rename(columns={"close": "idx_close"})
    merged = s.merge(i, on="time", how="inner")
    if len(merged) < lookback + 1:
        return None
    tail = merged.tail(lookback + 1)
    s0, s1 = float(tail["close"].iloc[0]), float(tail["close"].iloc[-1])
    i0, i1 = float(tail["idx_close"].iloc[0]), float(tail["idx_close"].iloc[-1])
    if s0 == 0 or i0 == 0:
        return None
    stock_ret = s1 / s0 - 1
    idx_ret = i1 / i0 - 1
    return round((stock_ret - idx_ret) * 100, 2)


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    """Thêm toàn bộ cột chỉ báo dùng trên đồ thị và bảng dòng tiền."""
    w = frame.copy()
    for col in ("open", "high", "low", "close", "volume"):
        w[col] = pd.to_numeric(w[col], errors="coerce")
    w["MA20"] = sma(w["close"], C.MA_SHORT)
    w["MA50"] = sma(w["close"], C.MA_MID)
    w["MA150"] = sma(w["close"], C.MA_LONG)
    w["BB_L"], w["BB_M"], w["BB_U"] = bollinger(w["close"])
    w["RSI"] = rsi(w["close"])
    w["MACD"], w["MACD_SIG"], w["MACD_HIST"] = macd(w["close"])
    w["OBV"] = obv(w["close"], w["volume"])
    w["MFI"] = mfi(w["high"], w["low"], w["close"], w["volume"])
    w["VOL_AVG"] = sma(w["volume"], C.VOLUME_AVG)
    return w


def money_flow_summary(w: pd.DataFrame) -> dict[str, object]:
    """Tóm tắt dòng tiền phiên cuối từ khung đã enrich."""
    last = w.iloc[-1]
    vol_ratio = float(last["volume"] / last["VOL_AVG"]) if last["VOL_AVG"] else float("nan")
    obv_tail = w["OBV"].tail(C.VOLUME_AVG)
    obv_slope = float(obv_tail.iloc[-1] - obv_tail.iloc[0]) if len(obv_tail) > 1 else 0.0
    return {
        "rsi": float(last["RSI"]),
        "mfi": float(last["MFI"]),
        "macd": float(last["MACD"]),
        "macd_signal": float(last["MACD_SIG"]),
        "macd_hist": float(last["MACD_HIST"]),
        "vol_ratio": vol_ratio,
        "obv_up": obv_slope > 0,
    }


def rsi_bottoms(values: pd.Series, zone: float, order: int = 3, lookback: int = 60) -> dict[str, object]:
    """Đáy RSI trong vùng quá bán và "đáy trung tâm" của RSI (F1 mục 7, hàng 2).

    Đáy = cực tiểu cục bộ trong ±order phiên, giá trị <= zone, các đáy cách nhau >= order phiên.
    Đáy trung tâm dùng cùng định nghĩa với analysis.support: đỉnh RSI cao nhất giữa
    đáy đầu và đáy cuối. crossed = RSI phiên cuối vừa vượt lên trên mức đó.
    """
    series = pd.to_numeric(values, errors="coerce").tail(lookback).reset_index(drop=True)
    data = series.to_numpy(dtype=float)
    bottoms: list[int] = []
    for index in range(order, len(data) - order):
        window = data[index - order : index + order + 1]
        if pd.isna(window).any() or data[index] > zone or data[index] != window.min():
            continue
        if bottoms and index - bottoms[-1] < order:
            continue
        bottoms.append(index)
    result: dict[str, object] = {
        "bottoms": len(bottoms),
        "bottom_values": [round(float(data[index]), 2) for index in bottoms],
        "neckline": None,
        "crossed": False,
        "last": None if len(data) == 0 or pd.isna(data[-1]) else round(float(data[-1]), 2),
    }
    if len(bottoms) >= 2 and len(data) >= 2 and not pd.isna(data[-2:]).any():
        neckline = float(max(data[bottoms[0] : bottoms[-1] + 1]))
        result["neckline"] = round(neckline, 2)
        result["crossed"] = bool(data[-2] <= neckline < data[-1])
    return result


def macd_improving(line: pd.Series, signal: pd.Series, hist: pd.Series, cross_window: int = 3, improve_bars: int = 2) -> dict[str, object]:
    """MACD cắt lên Signal gần đây + histogram tăng liên tiếp >= improve_bars phiên (F1 mục 7, hàng 3).

    cross_ago = số phiên kể từ lần MACD cắt lên Signal (0 = phiên cuối), None nếu không có
    trong cross_window phiên. improving = hist tăng đều improve_bars phiên gần nhất.
    """
    need = max(cross_window, improve_bars) + 1
    tail_line, tail_sig, tail_hist = line.tail(need + 1), signal.tail(need + 1), hist.tail(need + 1)
    if len(tail_hist) < need + 1 or tail_line.isna().any() or tail_sig.isna().any() or tail_hist.isna().any():
        raise ValueError(f"cần ít nhất {need + 1} phiên có MACD/Signal")
    above = (tail_line > tail_sig).to_numpy()
    cross_ago = None
    for ago in range(cross_window):
        index = len(above) - 1 - ago
        if above[index] and not above[index - 1]:
            cross_ago = ago
            break
    values = tail_hist.to_numpy(dtype=float)[-(improve_bars + 1) :]
    improving = bool(all(values[i + 1] > values[i] for i in range(improve_bars)))
    return {
        "cross_ago": cross_ago,
        "above": bool(above[-1]),
        "improving": improving,
        "histogram": round(float(values[-1]), 4),
    }
