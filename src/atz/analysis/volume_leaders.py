"""Top mã đột biến khối lượng so với TB 10 phiên (F1 mục 5).

Chỉ đọc OHLCV local — không gọi mạng. TB 10 = trung bình 10 phiên
trước phiên cuối; điều kiện sàn: TB ≥ min_avg.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import BARS_DIR, SPARKLINE_BARS, VOLUME_LEADERS_AVG, VOLUME_LEADERS_MIN_AVG, VOLUME_LEADERS_TOP_N
from datasource.spark_series import closes_sparkline
from engine.runner import load_symbol_csv

COLUMNS = (
    "Mã",
    "Giá",
    "KL phiên",
    "KL TB 10 phiên",
    "KL / TB10",
    "Biến động giá (%)",
    "Xu hướng",
)


def volume_stats(
    bars: pd.DataFrame,
    avg_bars: int = VOLUME_LEADERS_AVG,
) -> dict[str, float] | None:
    """Trả KL phiên cuối, TB avg_bars phiên trước, tỷ lệ, % giá. Thiếu dữ liệu → None."""
    if bars is None or bars.empty:
        return None
    if "volume" not in bars.columns or "close" not in bars.columns:
        return None
    volume = pd.to_numeric(bars["volume"], errors="coerce").dropna()
    close = pd.to_numeric(bars["close"], errors="coerce").dropna()
    need = avg_bars + 1
    if len(volume) < need or len(close) < 2:
        return None
    last_vol = float(volume.iloc[-1])
    prior = volume.iloc[-(avg_bars + 1) : -1]
    if len(prior) < avg_bars:
        return None
    avg = float(prior.mean())
    if avg <= 0:
        return None
    last_px = float(close.iloc[-1])
    prev_px = float(close.iloc[-2])
    change = ((last_px / prev_px) - 1.0) * 100 if prev_px else 0.0
    return {
        "price": last_px,
        "last_volume": last_vol,
        "avg_volume": avg,
        "ratio": last_vol / avg,
        "change_pct": change,
    }


def rank_volume_leaders(
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    min_avg: float = VOLUME_LEADERS_MIN_AVG,
    top_n: int = VOLUME_LEADERS_TOP_N,
    avg_bars: int = VOLUME_LEADERS_AVG,
) -> pd.DataFrame:
    """Xếp hạng theo KL/TB10 giảm dần, lọc TB ≥ min_avg."""
    root = bars_dir if bars_dir is not None else BARS_DIR
    if symbols is None:
        codes = sorted(path.stem.upper() for path in root.glob("*.csv") if path.stem)
    else:
        codes = [str(item).strip().upper() for item in symbols if str(item).strip()]
    rows: list[dict[str, object]] = []
    for symbol in codes:
        try:
            frame = load_symbol_csv(root, symbol)
        except Exception:
            continue
        stats = volume_stats(frame, avg_bars=avg_bars)
        if stats is None:
            continue
        if stats["avg_volume"] < min_avg:
            continue
        rows.append(
            {
                "Mã": symbol,
                "Giá": round(stats["price"], 2),
                "KL phiên": round(stats["last_volume"], 0),
                "KL TB 10 phiên": round(stats["avg_volume"], 0),
                "KL / TB10": round(stats["ratio"], 2),
                "Biến động giá (%)": round(stats["change_pct"], 2),
                "Xu hướng": closes_sparkline(frame, n=SPARKLINE_BARS),
            }
        )
    if not rows:
        return pd.DataFrame(columns=list(COLUMNS))
    board = pd.DataFrame(rows)
    return (
        board.sort_values("KL / TB10", ascending=False)
        .head(top_n)[list(COLUMNS)]
        .reset_index(drop=True)
    )
