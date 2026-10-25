"""Chấm điểm cố vấn 0–100 (xu hướng / dòng tiền / KT ngắn hạn)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

import config as C
from analysis.technical import bollinger, macd, macd_improving, rsi, sma
from storage.paths import repo_root


@dataclass(frozen=True)
class AdvisorScore:
    total: float | None
    pillars: dict[str, Any]
    recommendation: str
    reason: str
    flow_partial: bool = False


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@lru_cache(maxsize=1)
def default_config_path() -> Path:
    return repo_root() / "config" / "advisor_score.yaml"


@lru_cache(maxsize=4)
def load_advisor_config(path: str | None = None) -> dict[str, Any]:
    target = Path(path) if path else default_config_path()
    if not target.is_file():
        raise FileNotFoundError(f"Thiếu config advisor: {target}")
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    block = raw.get("advisor_score")
    if not isinstance(block, dict):
        raise ValueError("advisor_score.yaml: thiếu khóa advisor_score")
    return block


def resolve_advisor_params(params: dict[str, Any] | None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_advisor_config()
    merged = _deep_merge(cfg, dict(params or {}))
    weights = merged.get("weights") or {}
    for name in ("trend", "flow", "short_term"):
        weights.setdefault(name, {"trend": 0.4, "flow": 0.3, "short_term": 0.3}[name])
    merged["weights"] = weights
    return merged


def min_bars_needed(cfg: dict[str, Any]) -> int:
    trend = cfg["trend"]
    flow = cfg["flow"]
    st = cfg["short_term"]
    return (
        max(
            int(trend["ma_slow"]),
            int(flow["volume_avg"]),
            int(st["rsi_length"]),
            int(st["bb_length"]),
            C.MACD_SLOW + C.MACD_SIGNAL + int(st["macd_improve_bars"]),
        )
        + 2
    )


def _pillar_block(points: float, max_points: float, breakdown: dict[str, Any]) -> dict[str, Any]:
    return {
        "points": round(points, 1),
        "max": round(max_points, 1),
        "breakdown": breakdown,
    }


def _ma_cross_up_recent(fast: pd.Series, slow: pd.Series, window: int) -> bool:
    for ago in range(window):
        index = len(fast) - 1 - ago
        if index < 1:
            continue
        if fast.iloc[index] > slow.iloc[index] and fast.iloc[index - 1] <= slow.iloc[index - 1]:
            return True
    return False


def _score_trend(bars: pd.DataFrame, cfg: dict[str, Any], weight: float) -> tuple[float, dict[str, Any]]:
    max_pts = weight * 100.0
    tcfg = cfg["trend"]
    close = pd.to_numeric(bars["close"], errors="coerce")
    ma_fast = sma(close, int(tcfg["ma_fast"]))
    ma_slow = sma(close, int(tcfg["ma_slow"]))
    if pd.isna(ma_fast.iloc[-1]) or pd.isna(ma_slow.iloc[-1]):
        return 0.0, {"error": "thiếu MA"}
    last_close = float(close.iloc[-1])
    last_fast = float(ma_fast.iloc[-1])
    last_slow = float(ma_slow.iloc[-1])
    points = 0.0
    above_fast = last_close > last_fast
    fast_above_slow = last_fast > last_slow
    if above_fast:
        points += max_pts * 0.40
    if fast_above_slow:
        points += max_pts * 0.40
    cross_recent = _ma_cross_up_recent(ma_fast, ma_slow, int(tcfg.get("cross_window", 2)))
    if cross_recent:
        points += max_pts * 0.20
    breakdown = {
        "close": round(last_close, 4),
        "ma_fast": round(last_fast, 4),
        "ma_slow": round(last_slow, 4),
        "above_ma_fast": above_fast,
        "ma_fast_above_slow": fast_above_slow,
        "golden_cross_recent": cross_recent,
    }
    return points, breakdown


def _score_flow(bars: pd.DataFrame, cfg: dict[str, Any], weight: float) -> tuple[float, dict[str, Any], bool]:
    max_pts = weight * 100.0
    fcfg = cfg["flow"]
    volume = pd.to_numeric(bars["volume"], errors="coerce")
    vol_avg = sma(volume, int(fcfg["volume_avg"]))
    if pd.isna(vol_avg.iloc[-1]) or float(vol_avg.iloc[-1]) == 0:
        return 0.0, {"volume": "thiếu trung bình KL"}, False
    ratio = float(volume.iloc[-1]) / float(vol_avg.iloc[-1])
    spike = float(fcfg["volume_spike"])
    vol_frac = min(ratio / spike, 1.0) if spike > 0 else 0.0
    vol_points = max_pts * 0.5 * vol_frac

    column = "foreign_net_vol"
    flow_partial = column not in bars.columns
    foreign_points = 0.0
    foreign_breakdown: dict[str, Any] = {"available": not flow_partial}
    if not flow_partial:
        days = int(fcfg["foreign_days"])
        series = pd.to_numeric(bars[column], errors="coerce")
        tail = series.iloc[-days:]
        if tail.isna().any() or len(tail) < days:
            foreign_breakdown["streak"] = "thiếu dữ liệu"
        else:
            floor = float(fcfg["foreign_min_net_vol"])
            positives = (tail > floor).sum()
            foreign_frac = positives / days
            foreign_points = max_pts * 0.5 * foreign_frac
            foreign_breakdown = {
                "available": True,
                "days": days,
                "positive_days": int(positives),
                "last_net_vol": round(float(tail.iloc[-1]), 2),
            }
        points = foreign_points + vol_points
    else:
        vol_points = max_pts * vol_frac
        points = vol_points
    breakdown = {
        "volume_ratio": round(ratio, 2),
        "volume_spike_target": spike,
        "foreign": foreign_breakdown,
    }
    return points, breakdown, flow_partial


def _rsi_buy_fraction(value: float, zone: tuple[float, float]) -> float:
    low, high = zone
    if value < low:
        return max(0.0, 1.0 - (low - value) / max(low, 1.0))
    if value > high:
        return max(0.0, 1.0 - (value - high) / max(100.0 - high, 1.0))
    mid = (low + high) / 2.0
    return 1.0 - abs(value - mid) / max((high - low) / 2.0, 1.0)


def _bb_buy_fraction(close: float, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.0
    pct_b = (close - lower) / (upper - lower)
    if pct_b <= 0.2:
        return pct_b / 0.2
    if pct_b <= 0.55:
        return 1.0
    if pct_b >= 1.0:
        return max(0.0, 1.0 - (pct_b - 1.0))
    return max(0.0, 1.0 - (pct_b - 0.55) / 0.45)


def _score_short_term(bars: pd.DataFrame, cfg: dict[str, Any], weight: float) -> tuple[float, dict[str, Any]]:
    max_pts = weight * 100.0
    scfg = cfg["short_term"]
    close = pd.to_numeric(bars["close"], errors="coerce")
    rsi_len = int(scfg["rsi_length"])
    rsi_series = rsi(close, rsi_len)
    if pd.isna(rsi_series.iloc[-1]):
        return 0.0, {"error": "thiếu RSI"}
    rsi_val = float(rsi_series.iloc[-1])
    zone = tuple(float(x) for x in scfg["rsi_buy_zone"])
    rsi_frac = _rsi_buy_fraction(rsi_val, zone)
    rsi_points = max_pts * (1.0 / 3.0) * rsi_frac

    bb_len = int(scfg["bb_length"])
    bb_k = float(scfg["bb_k"])
    lower, mid, upper = bollinger(close, bb_len, bb_k)
    if pd.isna(lower.iloc[-1]) or pd.isna(upper.iloc[-1]):
        bb_points = 0.0
        pct_b = None
    else:
        last_close = float(close.iloc[-1])
        pct_b = (last_close - float(lower.iloc[-1])) / (float(upper.iloc[-1]) - float(lower.iloc[-1]))
        bb_frac = _bb_buy_fraction(last_close, float(lower.iloc[-1]), float(upper.iloc[-1]))
        bb_points = max_pts * (1.0 / 3.0) * bb_frac

    line, sig, hist = macd(close, C.MACD_FAST, C.MACD_SLOW, C.MACD_SIGNAL)
    macd_points = 0.0
    macd_breakdown: dict[str, Any] = {}
    try:
        scan = macd_improving(
            line,
            sig,
            hist,
            int(scfg.get("macd_cross_window", 3)),
            int(scfg.get("macd_improve_bars", 2)),
        )
        macd_frac = 0.0
        if scan.get("improving"):
            macd_frac += 0.6
        if scan.get("cross_ago") is not None:
            macd_frac += 0.4
        macd_points = max_pts * (1.0 / 3.0) * min(macd_frac, 1.0)
        macd_breakdown = scan
    except ValueError as exc:
        macd_breakdown = {"error": str(exc)}

    points = rsi_points + bb_points + macd_points
    breakdown = {
        "rsi": round(rsi_val, 2),
        "rsi_buy_zone": list(zone),
        "pct_b": round(float(pct_b), 3) if pct_b is not None else None,
        "macd": macd_breakdown,
    }
    return points, breakdown


def _recommendation(total: float, cfg: dict[str, Any]) -> str:
    th = cfg["thresholds"]
    if total >= float(th["buy_min_total"]):
        return "mua"
    if total <= float(th["sell_max_total"]):
        return "ban"
    return "giu"


def _summary_reason(score: AdvisorScore) -> str:
    if score.total is None:
        return score.reason
    trend = score.pillars["trend"]["points"]
    flow = score.pillars["flow"]["points"]
    short = score.pillars["short_term"]["points"]
    return f"Điểm {score.total:.1f}: xu hướng {trend:.1f}, dòng tiền {flow:.1f}, KT {short:.1f} → {score.recommendation}"


def compute_advisor_score(
    bars: pd.DataFrame,
    params: dict[str, Any] | None = None,
    *,
    config: dict[str, Any] | None = None,
    config_path: str | None = None,
) -> AdvisorScore:
    """Trả AdvisorScore; total=None khi thiếu nến hoặc cột bắt buộc."""
    if bars is None or bars.empty or "close" not in bars.columns:
        return AdvisorScore(None, {}, "cho", "không đủ dữ liệu")
    cfg = resolve_advisor_params(params, config or load_advisor_config(config_path))
    need = min_bars_needed(cfg)
    if len(bars) < need:
        return AdvisorScore(None, {}, "cho", "không đủ dữ liệu")

    weights = cfg["weights"]
    w_trend = float(weights["trend"])
    w_flow = float(weights["flow"])
    w_short = float(weights["short_term"])

    trend_pts, trend_bd = _score_trend(bars, cfg, w_trend)
    flow_pts, flow_bd, flow_partial = _score_flow(bars, cfg, w_flow)
    short_pts, short_bd = _score_short_term(bars, cfg, w_short)

    total = round(trend_pts + flow_pts + short_pts, 1)
    pillars = {
        "trend": _pillar_block(trend_pts, w_trend * 100.0, trend_bd),
        "flow": _pillar_block(flow_pts, w_flow * 100.0, {**flow_bd, "flow_partial": flow_partial}),
        "short_term": _pillar_block(short_pts, w_short * 100.0, short_bd),
    }
    rec = _recommendation(total, cfg)
    draft = AdvisorScore(total, pillars, rec, "", flow_partial=flow_partial)
    return AdvisorScore(total, pillars, rec, _summary_reason(draft), flow_partial=flow_partial)
