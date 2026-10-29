"""Native daily technical alerts for F3 (MA, Bollinger, Ichimoku, swing S/R).

Levels in the phrase are VND, same rule as portfolio quotes: OHLCV below 1000
is nghìn đồng and is multiplied by 1000. Config lives in ``config/f3_alerts.yaml``.
"""

from __future__ import annotations

import math
import os
from copy import deepcopy
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "f3_alerts.yaml"
F3_ALERTS_PATH = Path(os.getenv("F3_ALERTS_CONFIG", str(_DEFAULT_PATH)))

_DEFAULTS: dict = {
    "ma_periods": [20, 50, 100, 200],
    "min_bars": 20,
    "bollinger": {"period": 20, "stdev": 2.0, "mid_band": 0.15, "stdev_ddof": 0},
    "ichimoku": {"tenkan": 9, "kijun": 26, "senkou_b": 52, "displacement": 26},
    "swing": {"lookback": 5, "near_pct": 1.5},
}


def _positive_int(value: object, fallback: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def _positive_float(value: object, fallback: float) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def _merge_config(raw: object) -> dict:
    cfg = deepcopy(_DEFAULTS)
    if not isinstance(raw, dict):
        return cfg
    periods = raw.get("ma_periods")
    if isinstance(periods, list):
        cleaned = [_positive_int(item, 0) for item in periods]
        cleaned = [item for item in cleaned if item > 0]
        if cleaned:
            cfg["ma_periods"] = cleaned
    if "min_bars" in raw:
        cfg["min_bars"] = _positive_int(raw.get("min_bars"), cfg["min_bars"])
    for key in ("bollinger", "ichimoku", "swing"):
        incoming = raw.get(key)
        if not isinstance(incoming, dict):
            continue
        for field, fallback in cfg[key].items():
            if field not in incoming:
                continue
            if isinstance(fallback, int) and not isinstance(fallback, bool):
                cfg[key][field] = _positive_int(incoming[field], fallback)
            else:
                cfg[key][field] = _positive_float(incoming[field], float(fallback))
    # mid_band is a fraction in (0, 0.5]; 0 would make «BB giữa» unreachable.
    band = float(cfg["bollinger"]["mid_band"])
    cfg["bollinger"]["mid_band"] = min(max(band, 0.01), 0.5)
    return cfg


def load_f3_alert_config(path: Path | None = None) -> dict:
    """YAML thresholds. Missing or broken file falls back to built-in defaults."""
    target = path or F3_ALERTS_PATH
    if not target.is_file():
        return deepcopy(_DEFAULTS)
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return deepcopy(_DEFAULTS)
    return _merge_config(raw)


def _desk_level_vnd(value: float) -> str | None:
    """Parity ``portfolio_quotes._desk_to_vnd`` — phrase uses SPA price units."""
    if not math.isfinite(value) or value <= 0:
        return None
    vnd = round(value) if value >= 1000 else round(value * 1000)
    if vnd <= 0:
        return None
    return f"{int(vnd):,}"


def _trim_to_session(frame: pd.DataFrame, session_date: date | None) -> pd.DataFrame:
    if session_date is None or frame.empty:
        return frame
    col = next((name for name in frame.columns if str(name).lower() in {"time", "date", "trading_date"}), None)
    if col is None:
        return frame
    parsed = pd.to_datetime(frame[col], errors="coerce")
    if parsed.isna().all():
        return frame
    return frame.loc[parsed.dt.date <= session_date]


def _ohlcv(frame: pd.DataFrame) -> pd.DataFrame | None:
    lookup = {str(name).lower(): name for name in frame.columns}
    if any(key not in lookup for key in ("high", "low", "close")):
        return None
    out = pd.DataFrame(
        {
            "high": pd.to_numeric(frame[lookup["high"]], errors="coerce"),
            "low": pd.to_numeric(frame[lookup["low"]], errors="coerce"),
            "close": pd.to_numeric(frame[lookup["close"]], errors="coerce"),
        }
    )
    out = out.dropna(subset=["high", "low", "close"])
    if out.empty:
        return None
    return out.reset_index(drop=True)


def _ma_clause(close: pd.Series, periods: list[int]) -> str | None:
    last = float(close.iloc[-1])
    above: list[int] = []
    below: list[int] = []
    for period in periods:
        if len(close) < period:
            continue
        ma = float(close.rolling(period).mean().iloc[-1])
        if not math.isfinite(ma):
            continue
        if last > ma:
            above.append(period)
        elif last < ma:
            below.append(period)
    if above and not below:
        return f"Giá trên MA{max(above)}"
    if below and not above:
        return f"Giá dưới MA{min(below)}"
    if above and below:
        return f"Giá trên MA{max(above)} · dưới MA{min(below)}"
    return None


def _bb_clause(close: pd.Series, cfg: dict) -> str | None:
    period = int(cfg["period"])
    if len(close) < period:
        return None
    stdev = float(cfg["stdev"])
    ddof = int(cfg["stdev_ddof"])
    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=ddof)
    last = float(close.iloc[-1])
    middle = float(mid.iloc[-1])
    sigma = float(std.iloc[-1]) if pd.notna(std.iloc[-1]) else float("nan")
    if not math.isfinite(middle) or not math.isfinite(sigma):
        return None
    upper = middle + stdev * sigma
    lower = middle - stdev * sigma
    width = upper - lower
    if width <= 0:
        return "BB giữa"
    if last >= upper:
        return "BB trên"
    if last <= lower:
        return "BB dưới"
    pos = (last - lower) / width
    if abs(pos - 0.5) <= float(cfg["mid_band"]):
        return "BB giữa"
    if last > middle:
        return "BB nửa trên"
    return "BB nửa dưới"


def _ichimoku_clause(high: pd.Series, low: pd.Series, close: pd.Series, cfg: dict) -> str | None:
    tenkan_n = int(cfg["tenkan"])
    kijun_n = int(cfg["kijun"])
    senkou_n = int(cfg["senkou_b"])
    disp = int(cfg["displacement"])
    if len(close) < senkou_n + disp:
        return None
    tenkan = (high.rolling(tenkan_n).max() + low.rolling(tenkan_n).min()) / 2
    kijun = (high.rolling(kijun_n).max() + low.rolling(kijun_n).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(disp)
    span_b = ((high.rolling(senkou_n).max() + low.rolling(senkou_n).min()) / 2).shift(disp)
    cloud_a = float(span_a.iloc[-1])
    cloud_b = float(span_b.iloc[-1])
    if not math.isfinite(cloud_a) or not math.isfinite(cloud_b):
        return None
    t_prev, t_now = float(tenkan.iloc[-2]), float(tenkan.iloc[-1])
    k_prev, k_now = float(kijun.iloc[-2]), float(kijun.iloc[-1])
    if all(math.isfinite(v) for v in (t_prev, t_now, k_prev, k_now)):
        if t_prev <= k_prev and t_now > k_now:
            return "TK cắt lên KJ"
        if t_prev >= k_prev and t_now < k_now:
            return "TK cắt xuống KJ"
    last = float(close.iloc[-1])
    top, bot = max(cloud_a, cloud_b), min(cloud_a, cloud_b)
    if last > top:
        return "trên mây Ichimoku"
    if last < bot:
        return "dưới mây Ichimoku"
    return "trong mây Ichimoku"


def _swing_clause(high: pd.Series, low: pd.Series, close: pd.Series, cfg: dict) -> str | None:
    lookback = int(cfg["lookback"])
    near_pct = float(cfg["near_pct"])
    n = len(close)
    if n < lookback * 2 + 1:
        return None
    last = float(close.iloc[-1])
    if not math.isfinite(last) or last <= 0:
        return None
    highs = high.to_numpy()
    lows = low.to_numpy()
    last_confirmed = n - 1 - lookback
    resistances: list[float] = []
    supports: list[float] = []
    for index in range(lookback, last_confirmed + 1):
        h_win = highs[index - lookback : index + lookback + 1]
        l_win = lows[index - lookback : index + lookback + 1]
        if highs[index] == h_win.max() and highs[index] > highs[index - 1] and highs[index] > highs[index + 1]:
            resistances.append(float(highs[index]))
        if lows[index] == l_win.min() and lows[index] < lows[index - 1] and lows[index] < lows[index + 1]:
            supports.append(float(lows[index]))
    res = min((level for level in resistances if level > last), default=None)
    sup = max((level for level in supports if level < last), default=None)
    candidates: list[tuple[str, float, float]] = []
    if res is not None:
        candidates.append(("kháng cự", res, abs(res - last)))
    if sup is not None:
        candidates.append(("hỗ trợ", sup, abs(sup - last)))
    if not candidates:
        return None
    kind, level, _distance = min(candidates, key=lambda item: item[2])
    label = _desk_level_vnd(level)
    if label is None:
        return None
    near = abs(level - last) / last * 100 <= near_pct
    return f"gần {kind} {label}" if near else f"{kind} {label}"


def alert_column_for_bars(
    symbol: str,
    bars: pd.DataFrame | None,
    *,
    session_date: date | None = None,
    config: dict | None = None,
) -> str:
    """One status line for the F3 alert column. ``—`` when bars are unusable."""
    _ = symbol  # kept so callers match the previous (symbol, bars) shape
    if bars is None or not isinstance(bars, pd.DataFrame) or bars.empty:
        return "—"
    cfg = config or load_f3_alert_config()
    scoped = _trim_to_session(bars, session_date)
    if scoped.empty:
        return "—"
    ohlcv = _ohlcv(scoped)
    if ohlcv is None or len(ohlcv) < int(cfg["min_bars"]):
        return "—"
    parts: list[str] = []
    ma = _ma_clause(ohlcv["close"], list(cfg["ma_periods"]))
    if ma:
        parts.append(ma)
    bb = _bb_clause(ohlcv["close"], cfg["bollinger"])
    if bb:
        parts.append(bb)
    cloud = _ichimoku_clause(ohlcv["high"], ohlcv["low"], ohlcv["close"], cfg["ichimoku"])
    if cloud:
        parts.append(cloud)
    swing = _swing_clause(ohlcv["high"], ohlcv["low"], ohlcv["close"], cfg["swing"])
    if swing:
        parts.append(swing)
    return " · ".join(parts) if parts else "—"
