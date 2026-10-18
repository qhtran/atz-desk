"""Feature thanh khoản / biến động từ OHLCV cache riêng của tool."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from common import UniverseConfig, safe_log1p


def load_bars(bars_dir: Path, symbol: str) -> pd.DataFrame | None:
    path = bars_dir / f"{symbol.upper()}.csv"
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path)
    except Exception:
        return None
    if frame.empty or "close" not in frame.columns or "volume" not in frame.columns:
        return None
    work = frame.copy()
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work["volume"] = pd.to_numeric(work["volume"], errors="coerce")
    if "high" in work.columns:
        work["high"] = pd.to_numeric(work["high"], errors="coerce")
    if "low" in work.columns:
        work["low"] = pd.to_numeric(work["low"], errors="coerce")
    work = work.dropna(subset=["close", "volume"])
    return work if not work.empty else None


def atr_pct(frame: pd.DataFrame, window: int) -> float | None:
    if "high" not in frame.columns or "low" not in frame.columns:
        return None
    if len(frame) < window + 1:
        return None
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(tr.tail(window).mean())
    last = float(close.iloc[-1])
    if last <= 0 or atr != atr:
        return None
    return atr / last * 100.0


def feature_row(symbol: str, cfg: UniverseConfig) -> dict[str, float | str | None]:
    frame = load_bars(cfg.bars_dir, symbol)
    row: dict[str, float | str | None] = {
        "symbol": symbol.upper(),
        "bars": 0,
        "close": None,
        "vol20": None,
        "gtgd20": None,
        "atr_pct": None,
        "log_vol": 0.0,
        "log_gtgd": 0.0,
        "atr_score": 0.0,
        "has_bars": 0,
    }
    if frame is None or len(frame) < cfg.min_bars:
        return row
    window = cfg.volume_window
    vol = float(frame["volume"].tail(window).mean())
    close = float(frame["close"].iloc[-1])
    gtgd = vol * close  # proxy GTGD (đơn vị giá × cổ)
    atr = atr_pct(frame, cfg.atr_window)
    # ATR score: sweet spot ~1%–5% daily; ngoài khoảng giảm điểm.
    atr_score = 0.0
    if atr is not None:
        if 0.8 <= atr <= 5.0:
            atr_score = 1.0
        elif 0.4 <= atr < 0.8 or 5.0 < atr <= 8.0:
            atr_score = 0.5
        else:
            atr_score = 0.1
    row.update(
        {
            "bars": len(frame),
            "close": close,
            "vol20": vol,
            "gtgd20": gtgd,
            "atr_pct": atr,
            "log_vol": safe_log1p(vol),
            "log_gtgd": safe_log1p(gtgd),
            "atr_score": atr_score,
            "has_bars": 1,
        }
    )
    return row


def build_feature_table(symbols: list[str], cfg: UniverseConfig) -> pd.DataFrame:
    rows = [feature_row(symbol, cfg) for symbol in symbols]
    return pd.DataFrame(rows)


def zscore_series(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    mean = values.mean()
    std = values.std(ddof=0)
    if std is None or std == 0 or (isinstance(std, float) and std != std):
        return pd.Series([0.0] * len(values), index=values.index)
    return (values - mean) / std
