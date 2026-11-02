"""Vectorized real-time evaluation over in-memory tick rings (Option B)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StreamAlert:
    symbol: str
    timestamp: int
    indicator: str
    score: float
    risk_level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "alert",
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "indicator": self.indicator,
            "score": self.score,
            "risk_level": self.risk_level,
            "message": self.message,
        }


class TickRingStore:
    """Per-symbol ring of last prices / volumes (updated from live or mock ticks)."""

    def __init__(self, ring_size: int = 80) -> None:
        self.ring_size = max(20, int(ring_size))
        self._closes: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.ring_size)
        )
        self._volumes: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.ring_size)
        )

    def update(self, symbol: str, last: float | None, volume: float | None = None) -> None:
        sym = str(symbol or "").upper().strip()
        if not sym or last is None:
            return
        try:
            price = float(last)
        except (TypeError, ValueError):
            return
        if not np.isfinite(price):
            return
        self._closes[sym].append(price)
        try:
            vol = float(volume) if volume is not None else 0.0
        except (TypeError, ValueError):
            vol = 0.0
        self._volumes[sym].append(vol if np.isfinite(vol) else 0.0)

    def symbols(self) -> list[str]:
        return sorted(self._closes.keys())

    def close_frame(self, symbols: list[str] | None = None) -> pd.DataFrame:
        syms = symbols or self.symbols()
        cols: dict[str, pd.Series] = {}
        for sym in syms:
            buf = self._closes.get(sym)
            if not buf or len(buf) < 5:
                continue
            cols[sym] = pd.Series(list(buf), dtype=float)
        if not cols:
            return pd.DataFrame()
        return pd.DataFrame(cols)

    def volume_frame(self, symbols: list[str] | None = None) -> pd.DataFrame:
        syms = symbols or self.symbols()
        cols: dict[str, pd.Series] = {}
        for sym in syms:
            buf = self._volumes.get(sym)
            if not buf or len(buf) < 5:
                continue
            cols[sym] = pd.Series(list(buf), dtype=float)
        if not cols:
            return pd.DataFrame()
        return pd.DataFrame(cols)


def _rsi(close: pd.DataFrame, length: int) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _sma(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window=window, min_periods=window).mean()


def _risk_level(score: float, cfg: dict[str, Any]) -> str:
    levels = cfg.get("risk_levels") or {}
    high_below = float(levels.get("high_below", 40))
    low_above = float(levels.get("low_above", 70))
    if score >= low_above:
        return "LOW"
    if score <= high_below:
        return "HIGH"
    return "MEDIUM"


def evaluate_rings(store: TickRingStore, cfg: dict[str, Any]) -> list[StreamAlert]:
    """Pandas batch over all rings — no per-symbol Python scoring loop for indicators."""
    close = store.close_frame()
    if close.empty:
        return []
    volume = store.volume_frame(list(close.columns)).reindex(columns=close.columns)

    rsi_cfg = cfg.get("rsi") or {}
    ma_cfg = cfg.get("ma") or {}
    vol_cfg = cfg.get("volume_spike") or {}
    rsi_n = int(rsi_cfg.get("length", 14))
    oversold = float(rsi_cfg.get("oversold", 30))
    overbought = float(rsi_cfg.get("overbought", 70))
    ma_fast_n = int(ma_cfg.get("fast", 10))
    ma_slow_n = int(ma_cfg.get("slow", 20))
    vol_lb = int(vol_cfg.get("lookback", 20))
    vol_mult = float(vol_cfg.get("mult", 2.0))

    rsi = _rsi(close, rsi_n)
    last_rsi = rsi.iloc[-1]
    ma_fast = _sma(close, ma_fast_n).iloc[-1]
    ma_slow = _sma(close, ma_slow_n).iloc[-1]
    last_close = close.iloc[-1]

    vol_spike = pd.Series(False, index=close.columns)
    if not volume.empty and len(volume) >= max(5, vol_lb // 2):
        v_ma = volume.rolling(window=vol_lb, min_periods=max(5, vol_lb // 2)).mean().iloc[-1]
        v_last = volume.iloc[-1]
        vol_spike = (v_ma > 0) & (v_last >= v_ma * vol_mult)

    now = int(time.time())
    alerts: list[StreamAlert] = []

    # Build boolean masks then collect — packaging loop only
    oversold_mask = last_rsi <= oversold
    overbought_mask = last_rsi >= overbought
    golden_mask = (ma_fast > ma_slow) & (last_close > ma_fast)

    for sym in close.columns:
        r = last_rsi.get(sym)
        if r is None or (isinstance(r, float) and np.isnan(r)):
            continue
        rsi_val = float(r)
        # score: map RSI proximity to extremes + MA alignment (0–100)
        score = 50.0
        if bool(oversold_mask.get(sym, False)):
            score = min(100.0, 70.0 + (oversold - rsi_val))
            msg = f"RSI {rsi_val:.1f} chạm vùng quá bán"
            if bool(vol_spike.get(sym, False)):
                msg += " kèm khối lượng đột biến"
                score = min(100.0, score + 10.0)
            alerts.append(
                StreamAlert(
                    symbol=str(sym),
                    timestamp=now,
                    indicator="RSI_OVERSOLD",
                    score=round(score, 1),
                    risk_level=_risk_level(score, cfg),
                    message=msg,
                )
            )
        elif bool(overbought_mask.get(sym, False)):
            score = max(0.0, 30.0 - (rsi_val - overbought))
            alerts.append(
                StreamAlert(
                    symbol=str(sym),
                    timestamp=now,
                    indicator="RSI_OVERBOUGHT",
                    score=round(score, 1),
                    risk_level=_risk_level(score, cfg),
                    message=f"RSI {rsi_val:.1f} chạm vùng quá mua",
                )
            )
        if bool(golden_mask.get(sym, False)) and len(close[sym].dropna()) >= ma_slow_n:
            score_ma = 75.0 if bool(vol_spike.get(sym, False)) else 65.0
            alerts.append(
                StreamAlert(
                    symbol=str(sym),
                    timestamp=now,
                    indicator="MA_TREND_UP",
                    score=score_ma,
                    risk_level=_risk_level(score_ma, cfg),
                    message=f"MA{ma_fast_n}>MA{ma_slow_n} và giá trên MA nhanh",
                )
            )

    max_n = int(cfg.get("max_alerts_per_tick", 20))
    alerts.sort(key=lambda a: a.score, reverse=True)
    return alerts[:max_n]
