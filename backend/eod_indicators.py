"""Technical indicators (Pandas/NumPy) trên chuỗi EOD OHLCV — Milestone 3 Phase 2."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def ohlcv_to_frame(rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hoá DataFrame index ``trade_date``, cột OHLCV numeric."""
    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
    else:
        frame = pd.DataFrame(list(rows or []))
    if frame.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    rename = {}
    for col in frame.columns:
        key = str(col).lower()
        if key in {"date", "trading_date", "trade_date", "time"}:
            rename[col] = "trade_date"
        elif key in {"open", "high", "low", "close", "volume"}:
            rename[col] = key
    frame = frame.rename(columns=rename)
    if "trade_date" in frame.columns:
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
        frame = frame.dropna(subset=["trade_date"]).sort_values("trade_date")
        frame = frame.set_index("trade_date")
    for col in ("open", "high", "low", "close", "volume"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        else:
            frame[col] = np.nan
    return frame


def sma(series: pd.Series | list[float] | np.ndarray, window: int) -> pd.Series:
    s = pd.Series(series, dtype="float64")
    w = max(1, int(window))
    return s.rolling(window=w, min_periods=w).mean()


def ema(series: pd.Series | list[float] | np.ndarray, span: int) -> pd.Series:
    s = pd.Series(series, dtype="float64")
    n = max(1, int(span))
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(series: pd.Series | list[float] | np.ndarray, length: int = 14) -> pd.Series:
    """Wilder RSI (ewm alpha = 1/length)."""
    s = pd.Series(series, dtype="float64")
    n = max(1, int(length))
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out


def macd(
    series: pd.Series | list[float] | np.ndarray,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    s = pd.Series(series, dtype="float64")
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    hist = line - sig
    return pd.DataFrame({"macd": line, "signal": sig, "hist": hist})


def volume_spike(
    volume: pd.Series | list[float] | np.ndarray,
    *,
    lookback: int = 20,
    mult: float = 2.5,
) -> pd.DataFrame:
    """``ratio = volume / SMA(volume prior lookback)``; ``spike`` khi ratio >= mult.

    Baseline dùng SMA của ``lookback`` phiên **trước** nến hiện tại (không gồm volume hôm nay).
    """
    vol = pd.Series(volume, dtype="float64")
    lb = max(1, int(lookback))
    baseline = vol.shift(1).rolling(window=lb, min_periods=lb).mean()
    ratio = vol / baseline.replace(0.0, np.nan)
    spike = ratio >= float(mult)
    return pd.DataFrame({"volume": vol, "vol_sma": baseline, "ratio": ratio, "spike": spike})


def compute_indicator_bundle(
    rows: list[dict[str, Any]] | pd.DataFrame,
    *,
    sma_windows: tuple[int, ...] = (10, 20),
    ema_spans: tuple[int, ...] = (12, 26),
    rsi_length: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    vol_lookback: int = 20,
    vol_mult: float = 2.5,
) -> pd.DataFrame:
    """Trả DataFrame OHLCV + cột chỉ báo (cùng index ngày)."""
    frame = ohlcv_to_frame(rows)
    if frame.empty or "close" not in frame.columns:
        return frame
    close = frame["close"]
    for w in sma_windows:
        frame[f"sma_{int(w)}"] = sma(close, int(w))
    for sp in ema_spans:
        frame[f"ema_{int(sp)}"] = ema(close, int(sp))
    frame["rsi"] = rsi(close, rsi_length)
    macd_df = macd(close, fast=macd_fast, slow=macd_slow, signal=macd_signal)
    frame = frame.join(macd_df)
    if "volume" in frame.columns:
        vs = volume_spike(frame["volume"], lookback=vol_lookback, mult=vol_mult)
        frame["vol_sma"] = vs["vol_sma"]
        frame["vol_ratio"] = vs["ratio"]
        frame["vol_spike"] = vs["spike"]
    return frame
