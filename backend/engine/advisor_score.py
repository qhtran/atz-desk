"""Advisor scoring 0–100 — batch pandas (Hướng 1 / FILTER_SCORING_HUONG1).

Tính trụ trend / flow / short_term trên toàn panel (cột = mã), không vòng for
tính điểm từng mã. Đóng gói kết quả từ Series/DataFrame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AdvisorBatchResult:
    """Khung kết quả batch: index = symbol."""

    frame: pd.DataFrame

    def to_hit_rows(
        self,
        *,
        buy_min_total: float,
        risk_meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if self.frame.empty:
            return []
        ok = self.frame["score"].notna() & (self.frame["score"] >= float(buy_min_total))
        subset = self.frame.loc[ok].sort_values("score", ascending=False)
        meta = dict(risk_meta or {})
        records = subset.reset_index().rename(columns={"index": "symbol"}).to_dict(orient="records")
        rows: list[dict[str, Any]] = []
        for rec in records:
            score = float(rec["score"])
            rows.append(
                {
                    "symbol": str(rec["symbol"]).upper(),
                    "filter": "advisor",
                    "filters": ["advisor"],
                    "signal_type": str(rec.get("recommendation") or "giu"),
                    "reason": str(rec.get("reason") or ""),
                    "total": score,
                    "score": score,
                    "trend": float(rec.get("trend") or 0.0),
                    "flow": float(rec.get("flow") or 0.0),
                    "short_term": float(rec.get("short_term") or 0.0),
                    "risk_meta": meta,
                }
            )
        return rows


def _sma(df: pd.DataFrame, window: int) -> pd.DataFrame:
    return df.rolling(window=window, min_periods=window).mean()


def _rsi(close: pd.DataFrame, length: int) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _panels_to_frames(
    panels: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    foreigns: dict[str, pd.Series] = {}
    has_foreign = False
    for sym, bars in panels.items():
        if bars is None or bars.empty or "close" not in bars.columns:
            continue
        code = str(sym).upper()
        closes[code] = pd.to_numeric(bars["close"], errors="coerce").reset_index(drop=True)
        if "volume" in bars.columns:
            volumes[code] = pd.to_numeric(bars["volume"], errors="coerce").reset_index(drop=True)
        else:
            volumes[code] = pd.Series(np.nan, index=closes[code].index)
        if "foreign_net_vol" in bars.columns:
            has_foreign = True
            foreigns[code] = pd.to_numeric(bars["foreign_net_vol"], errors="coerce").reset_index(
                drop=True
            )
    if not closes:
        empty = pd.DataFrame()
        return empty, empty, None
    close = pd.DataFrame(closes)
    volume = pd.DataFrame(volumes).reindex(columns=close.columns)
    foreign = pd.DataFrame(foreigns).reindex(columns=close.columns) if has_foreign else None
    return close, volume, foreign


def score_frame_from_panels(
    panels: dict[str, pd.DataFrame],
    scoring_cfg: dict[str, Any],
) -> pd.DataFrame:
    """Trả DataFrame index=symbol: score, trend, flow, short_term, recommendation, reason."""
    close, volume, foreign = _panels_to_frames(panels)
    if close.empty:
        return pd.DataFrame(
            columns=["score", "trend", "flow", "short_term", "recommendation", "reason", "flow_partial"]
        )

    weights = scoring_cfg.get("weights") or {}
    w_trend = float(weights.get("trend", 0.4))
    w_flow = float(weights.get("flow", 0.3))
    w_st = float(weights.get("short_term", 0.3))

    tcfg = scoring_cfg.get("trend") or {}
    fcfg = scoring_cfg.get("flow") or {}
    scfg = scoring_cfg.get("short_term") or {}

    ma_fast_n = int(tcfg.get("ma_fast", 10))
    ma_slow_n = int(tcfg.get("ma_slow", 50))
    cross_n = int(tcfg.get("cross_window", 2))
    vol_avg_n = int(fcfg.get("volume_avg", 20))
    vol_spike = float(fcfg.get("volume_spike", 2.0))
    foreign_days = int(fcfg.get("foreign_days", 5))
    foreign_min = float(fcfg.get("foreign_min_net_vol", 0))
    rsi_n = int(scfg.get("rsi_length", 14))
    zone = scfg.get("rsi_buy_zone") or [30, 45]
    rsi_lo, rsi_hi = float(zone[0]), float(zone[1])
    rsi_sell = float(scfg.get("rsi_sell_above", 70))
    bb_n = int(scfg.get("bb_length", 20))
    bb_k = float(scfg.get("bb_k", 2.0))

    min_len = max(ma_slow_n, vol_avg_n, rsi_n, bb_n) + 2
    bar_count = close.notna().sum(axis=0)

    ma_fast = _sma(close, ma_fast_n)
    ma_slow = _sma(close, ma_slow_n)
    last_close = close.iloc[-1]
    last_fast = ma_fast.iloc[-1]
    last_slow = ma_slow.iloc[-1]

    # Trend pillar (max = w_trend * 100) — vectorized boolean → float
    max_trend = w_trend * 100.0
    above_fast = (last_close > last_fast).astype(float)
    fast_above_slow = (last_fast > last_slow).astype(float)
    # cross up bất kỳ trong cross_n phiên gần nhất (vectorized)
    fast_gt = ma_fast > ma_slow
    prev_gt = fast_gt.shift(1).fillna(False).astype(bool)
    cross_up = fast_gt.astype(bool) & (~prev_gt)
    cross = (
        cross_up.iloc[-cross_n:].any(axis=0).astype(float)
        if len(close) >= 2
        else pd.Series(0.0, index=close.columns)
    )
    trend_pts = (
        above_fast * (max_trend * 0.40)
        + fast_above_slow * (max_trend * 0.40)
        + cross * (max_trend * 0.20)
    )

    # Flow pillar
    max_flow = w_flow * 100.0
    vol_ma = _sma(volume, vol_avg_n)
    last_vol = volume.iloc[-1]
    last_vol_ma = vol_ma.iloc[-1]
    spike = (last_vol_ma > 0) & (last_vol / last_vol_ma >= vol_spike)
    flow_vol_pts = spike.astype(float) * (max_flow * 0.50)
    flow_partial = pd.Series(True, index=close.columns)
    flow_foreign_pts = pd.Series(0.0, index=close.columns)
    if foreign is not None and not foreign.empty:
        flow_partial = pd.Series(False, index=close.columns)
        window = foreign.iloc[-foreign_days:] if foreign_days > 0 else foreign.iloc[0:0]
        net = window.sum(axis=0, min_count=1)
        flow_foreign_pts = (net >= foreign_min).astype(float) * (max_flow * 0.50)
        # missing foreign series → partial + only volume half available
        missing = foreign.isna().all(axis=0)
        flow_partial = missing
        flow_foreign_pts = flow_foreign_pts.where(~missing, 0.0)
    flow_pts = flow_vol_pts + flow_foreign_pts

    # Short-term pillar
    max_st = w_st * 100.0
    rsi = _rsi(close, rsi_n)
    last_rsi = rsi.iloc[-1]
    in_buy = (last_rsi >= rsi_lo) & (last_rsi <= rsi_hi)
    overbought = last_rsi >= rsi_sell
    mid = _sma(close, bb_n)
    std = close.rolling(window=bb_n, min_periods=bb_n).std()
    upper = mid + bb_k * std
    lower = mid - bb_k * std
    last_mid = mid.iloc[-1]
    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]
    band = (last_upper - last_lower).replace(0.0, np.nan)
    pct_b = (last_close - last_lower) / band
    near_lower = pct_b <= 0.35
    st_pts = (
        in_buy.astype(float) * (max_st * 0.50)
        + near_lower.astype(float) * (max_st * 0.30)
        + (~overbought.astype(bool)).astype(float) * (max_st * 0.20)
    )

    enough = bar_count >= min_len
    total = trend_pts + flow_pts + st_pts
    total = total.where(enough, np.nan)

    buy_min = float(scoring_cfg.get("buy_min_total", 65))
    sell_max = float(scoring_cfg.get("sell_max_total", 35))
    recommendation = pd.Series("giu", index=close.columns)
    recommendation = recommendation.mask(total >= buy_min, "mua")
    recommendation = recommendation.mask(total <= sell_max, "ban")
    recommendation = recommendation.where(enough, "giu")

    reason = (
        "T"
        + trend_pts.round(0).fillna(0).astype(int).astype(str)
        + " F"
        + flow_pts.round(0).fillna(0).astype(int).astype(str)
        + " ST"
        + st_pts.round(0).fillna(0).astype(int).astype(str)
        + " Σ"
        + total.round(1).astype(str)
    )
    reason = reason.where(enough, "không đủ dữ liệu")

    out = pd.DataFrame(
        {
            "score": total.round(1),
            "trend": trend_pts.round(1),
            "flow": flow_pts.round(1),
            "short_term": st_pts.round(1),
            "recommendation": recommendation,
            "reason": reason,
            "flow_partial": flow_partial,
        },
        index=close.columns,
    )
    out.index.name = "symbol"
    return out


def hits_from_panels(
    panels: dict[str, pd.DataFrame],
    scoring_cfg: dict[str, Any],
    *,
    buy_min_total: float | None = None,
    risk_meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    frame = score_frame_from_panels(panels, scoring_cfg)
    floor = float(
        buy_min_total
        if buy_min_total is not None
        else scoring_cfg.get("buy_min_total", 65)
    )
    return AdvisorBatchResult(frame).to_hit_rows(buy_min_total=floor, risk_meta=risk_meta)
