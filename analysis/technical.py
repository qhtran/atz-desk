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
