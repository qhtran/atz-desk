"""EOD quantitative screener — vectorized Pandas scan over ``eod_prices``."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

from backend.eod_indicators import rsi, sma, volume_spike
from backend.eod_store import load_eod_universe

FILTER_CATALOG = [
    {
        "id": "rsi_lt",
        "label": "RSI oversold",
        "params": {"threshold": 30, "length": 14},
        "example": "RSI < 30",
    },
    {
        "id": "rsi_gt",
        "label": "RSI overbought",
        "params": {"threshold": 70, "length": 14},
        "example": "RSI > 70",
    },
    {
        "id": "close_gt_sma",
        "label": "Close above SMA",
        "params": {"period": 50},
        "example": "Close > SMA50 / SMA200",
    },
    {
        "id": "volume_spike",
        "label": "Volume spike",
        "params": {"lookback": 20, "mult": 2.5},
        "example": "Volume > mult * Volume_SMA",
    },
    {
        "id": "breakout_high",
        "label": "Breakout highest high",
        "params": {"period": 20},
        "example": "Close >= Highest High(period)",
    },
]


def _metrics_for_group(g: pd.DataFrame) -> dict[str, Any]:
    """Last-bar metrics for one symbol (called via groupby)."""
    close = pd.to_numeric(g["close"], errors="coerce")
    high = pd.to_numeric(g["high"], errors="coerce")
    vol = pd.to_numeric(g["volume"], errors="coerce")
    last_close = float(close.iloc[-1]) if len(close) else float("nan")
    last_high = float(high.iloc[-1]) if len(high) else float("nan")
    last_vol = float(vol.iloc[-1]) if len(vol) else float("nan")
    trade_date = str(g["trade_date"].iloc[-1])

    rsi14 = rsi(close, 14)
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    sma200 = sma(close, 200)
    vs = volume_spike(vol, lookback=20, mult=2.5)
    # Highest high of prior N bars (exclude today) — classic breakout.
    hh20 = high.shift(1).rolling(20, min_periods=20).max()
    hh55 = high.shift(1).rolling(55, min_periods=55).max()

    def _last(series: pd.Series) -> float:
        if series.empty:
            return float("nan")
        val = series.iloc[-1]
        try:
            f = float(val)
        except (TypeError, ValueError):
            return float("nan")
        return f if np.isfinite(f) else float("nan")

    return {
        "trade_date": trade_date,
        "close": last_close,
        "high": last_high,
        "volume": last_vol,
        "rsi_14": _last(rsi14),
        "sma_20": _last(sma20),
        "sma_50": _last(sma50),
        "sma_200": _last(sma200),
        "vol_sma_20": _last(vs["vol_sma"]),
        "vol_ratio_20": _last(vs["ratio"]),
        "hh_20": _last(hh20),
        "hh_55": _last(hh55),
        "bars": int(len(g)),
    }


def build_symbol_snapshot(
    rows: list[dict[str, Any]],
    *,
    min_bars: int = 30,
) -> pd.DataFrame:
    """Wide table 1 row/symbol với chỉ báo EOD mới nhất."""
    if not rows:
        return pd.DataFrame()
    raw = pd.DataFrame(rows)
    if raw.empty:
        return pd.DataFrame()
    raw["symbol"] = raw["symbol"].astype(str).str.upper()
    raw["trade_date"] = raw["trade_date"].astype(str)
    for col in ("open", "high", "low", "close", "volume"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw = raw.dropna(subset=["close"])
    if raw.empty:
        return pd.DataFrame()

    parts: list[dict[str, Any]] = []
    for sym, group in raw.groupby("symbol", sort=True):
        g = group.sort_values("trade_date")
        if len(g) < int(min_bars):
            continue
        metrics = _metrics_for_group(g)
        metrics["symbol"] = str(sym)
        parts.append(metrics)
    if not parts:
        return pd.DataFrame()
    return pd.DataFrame(parts).set_index("symbol", drop=False)


def _finite(val: Any) -> bool:
    try:
        return bool(np.isfinite(float(val)))
    except (TypeError, ValueError):
        return False


def apply_eod_filters(
    snapshot: pd.DataFrame,
    *,
    mode: str = "and",
    rsi_lt: float | None = None,
    rsi_gt: float | None = None,
    close_gt_sma: list[int] | None = None,
    volume_mult: float | None = None,
    volume_sma_period: int = 20,
    breakout_high_period: int | None = None,
) -> pd.DataFrame:
    """Apply dynamic filters; ``mode`` and/or across active criteria."""
    if snapshot is None or snapshot.empty:
        return pd.DataFrame()

    masks: list[pd.Series] = []
    df = snapshot

    if rsi_lt is not None:
        masks.append(df["rsi_14"].notna() & (df["rsi_14"] < float(rsi_lt)))
    if rsi_gt is not None:
        masks.append(df["rsi_14"].notna() & (df["rsi_14"] > float(rsi_gt)))

    for period in close_gt_sma or []:
        col = f"sma_{int(period)}"
        if col not in df.columns:
            # compute on the fly from close if only 20/50/200 precomputed — skip unknown
            continue
        masks.append(df["close"].notna() & df[col].notna() & (df["close"] > df[col]))

    if volume_mult is not None:
        period = int(volume_sma_period or 20)
        # snapshot has vol_ratio_20 for period=20; recompute ratio if needed
        if period == 20 and "vol_ratio_20" in df.columns:
            masks.append(df["vol_ratio_20"].notna() & (df["vol_ratio_20"] >= float(volume_mult)))
        elif "vol_sma_20" in df.columns and period == 20:
            ratio = df["volume"] / df["vol_sma_20"].replace(0, np.nan)
            masks.append(ratio.notna() & (ratio >= float(volume_mult)))
        else:
            # fallback: use vol_ratio_20
            masks.append(df["vol_ratio_20"].notna() & (df["vol_ratio_20"] >= float(volume_mult)))

    if breakout_high_period is not None:
        p = int(breakout_high_period)
        col = f"hh_{p}" if f"hh_{p}" in df.columns else ("hh_20" if p <= 20 else "hh_55")
        if col in df.columns:
            masks.append(df["close"].notna() & df[col].notna() & (df["close"] >= df[col]))

    if not masks:
        return df.copy()

    combined = masks[0]
    join_or = str(mode or "and").lower() == "or"
    for m in masks[1:]:
        combined = (combined | m) if join_or else (combined & m)
    return df.loc[combined].copy()


def run_eod_screener(
    *,
    mode: str = "and",
    rsi_lt: float | None = None,
    rsi_gt: float | None = None,
    close_gt_sma: list[int] | None = None,
    volume_mult: float | None = None,
    volume_sma_period: int = 20,
    breakout_high_period: int | None = None,
    symbols: list[str] | None = None,
    min_bars: int = 30,
    lookback_calendar_days: int = 400,
    db_path: Any = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    rows = load_eod_universe(
        lookback_calendar_days=lookback_calendar_days,
        symbols=symbols,
        db_path=db_path,
    )
    snap = build_symbol_snapshot(rows, min_bars=min_bars)
    matched = apply_eod_filters(
        snap,
        mode=mode,
        rsi_lt=rsi_lt,
        rsi_gt=rsi_gt,
        close_gt_sma=close_gt_sma,
        volume_mult=volume_mult,
        volume_sma_period=volume_sma_period,
        breakout_high_period=breakout_high_period,
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    out_rows = []
    for _, row in matched.iterrows():
        item = {k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in row.items()}
        # cast numpy types
        for key, val in list(item.items()):
            if hasattr(val, "item"):
                try:
                    item[key] = val.item()
                except Exception:
                    pass
        out_rows.append(item)
    return {
        "ok": True,
        "source": "eod_prices",
        "mode": mode,
        "scanned": int(len(snap)),
        "matched": len(out_rows),
        "elapsed_ms": elapsed_ms,
        "rows": out_rows,
        "filters": {
            "rsi_lt": rsi_lt,
            "rsi_gt": rsi_gt,
            "close_gt_sma": close_gt_sma or [],
            "volume_mult": volume_mult,
            "volume_sma_period": volume_sma_period,
            "breakout_high_period": breakout_high_period,
        },
    }
