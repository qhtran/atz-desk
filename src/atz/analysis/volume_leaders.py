"""Top mã đột biến khối lượng so với TB 10 phiên (F1 mục 5).

KL / TB10 từ OHLCV local. Giá + % ưu tiên Redis quote phiên (fallback OHLCV).
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

# Chỉ số / ETF hay lẫn trong data/ohlcv — không xếp Top KL cổ phiếu.
_EXCLUDE_SYMBOLS = frozenset(
    {
        "VNINDEX",
        "VN30",
        "VN100",
        "HNXINDEX",
        "HNX",
        "UPCOMINDEX",
        "UPCOM",
        "VN30F1M",
        "VN30F2M",
    }
)
_EXCLUDE_PREFIXES = (
    "VNINDEX",
    "VNINDE",  # nhãn UI cắt
    "HNXINDEX",
    "HNXINDE",
    "UPCOMINDEX",
    "UPCOMINDE",
    "VN30F",
)


def _normalize_leader_symbol(raw: object) -> str:
    return str(raw or "").strip().upper()


def is_index_symbol(raw: object) -> bool:
    """True nếu mã là chỉ số / phái sinh chỉ số — không đưa vào Top KL CP."""
    code = _normalize_leader_symbol(raw)
    if not code:
        return True
    if code in _EXCLUDE_SYMBOLS:
        return True
    return any(code.startswith(prefix) for prefix in _EXCLUDE_PREFIXES)


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


def bar_session_date(bars: pd.DataFrame) -> str | None:
    """Ngày phiên của nến cuối (cột ``time``). Không có → None."""
    if bars is None or bars.empty or "time" not in bars.columns:
        return None
    try:
        return pd.to_datetime(bars["time"].iloc[-1]).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def apply_live_price_overlay(
    board: pd.DataFrame,
    quotes: dict[str, dict[str, float]] | None,
) -> tuple[pd.DataFrame, int]:
    """Ghi đè Giá + Biến động giá (%) từ Redis session quotes. Trả (board, số mã overlay)."""
    if board is None or board.empty or not quotes:
        return board, 0
    work = board.copy()
    hits = 0
    for index, row in work.iterrows():
        symbol = str(row.get("Mã") or "").strip().upper()
        payload = quotes.get(symbol)
        if not payload:
            continue
        price_k = payload.get("price_k")
        change_pct = payload.get("change_pct")
        if price_k is None or change_pct is None:
            continue
        work.at[index, "Giá"] = round(float(price_k), 2)
        work.at[index, "Biến động giá (%)"] = round(float(change_pct), 2)
        hits += 1
    return work, hits


def rank_volume_leaders(
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    min_avg: float = VOLUME_LEADERS_MIN_AVG,
    top_n: int = VOLUME_LEADERS_TOP_N,
    avg_bars: int = VOLUME_LEADERS_AVG,
    *,
    live_quotes: dict[str, dict[str, float]] | None = None,
    use_live: bool = True,
) -> pd.DataFrame:
    """Xếp hạng theo KL/TB10 giảm dần, lọc TB ≥ min_avg.

    ``use_live``: True → overlay Giá/% từ Redis (hoặc ``live_quotes`` mock).
    attrs: ``ohlcv_session_date``, ``price_source``, ``redis_overlay_count``.
    """
    root = bars_dir if bars_dir is not None else BARS_DIR
    if symbols is None:
        codes = sorted(_normalize_leader_symbol(path.stem) for path in root.glob("*.csv") if path.stem)
    else:
        codes = [_normalize_leader_symbol(item) for item in symbols if str(item).strip()]
    codes = [c for c in codes if c and not is_index_symbol(c)]
    rows: list[dict[str, object]] = []
    session_dates: list[str] = []
    for symbol in codes:
        try:
            frame = load_symbol_csv(root, symbol)
        except Exception:
            continue
        if frame is None or getattr(frame, "empty", True):
            continue
        stats = volume_stats(frame, avg_bars=avg_bars)
        if stats is None:
            continue
        if stats["avg_volume"] < min_avg:
            continue
        day = bar_session_date(frame)
        if day:
            session_dates.append(day)
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
        empty = pd.DataFrame(columns=list(COLUMNS))
        empty.attrs["ohlcv_session_date"] = None
        empty.attrs["price_source"] = "ohlcv"
        empty.attrs["redis_overlay_count"] = 0
        return empty
    board = pd.DataFrame(rows)
    board = (
        board.sort_values("KL / TB10", ascending=False)
        .head(top_n)[list(COLUMNS)]
        .reset_index(drop=True)
    )
    quotes = live_quotes
    if quotes is None and use_live:
        try:
            from datasource.live_quotes import load_live_session_quotes

            quotes = load_live_session_quotes(board["Mã"].astype(str).tolist())
        except Exception:
            quotes = {}
    if quotes is None:
        quotes = {}
    board, hits = apply_live_price_overlay(board, quotes)
    board.attrs["ohlcv_session_date"] = max(session_dates) if session_dates else None
    board.attrs["price_source"] = "redis" if hits else "ohlcv"
    board.attrs["redis_overlay_count"] = int(hits)
    return board
