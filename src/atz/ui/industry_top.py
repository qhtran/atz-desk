"""Top 5 mã mỗi ngành trên universe hiện tại. Chỉ đọc file đã cache, không gọi mạng."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from analysis.candles import candle_pattern
from analysis.technical import bollinger, ichimoku, macd, mcdx, rsi, sma
from config import BARS_DIR, INDUSTRY_PATH, UNIVERSE
from datasource.kqkd import kqkd_cells
from engine.runner import load_symbol_csv
from ui.components import render_data_table

TOP_PER_INDUSTRY = 5
_RETURN_BARS = 20
_WEEK_BARS = 5
_MONTH_BARS = 21
_COLUMNS = (
    "Ngành",
    "Mã",
    "Xu hướng ngày",
    "Xu hướng tuần",
    "Xu hướng tháng",
    "Tín hiệu nến",
    "BB",
    "MA",
    "RSI",
    "MACD",
    "Mây",
    "MCDX",
    "Cường độ mua/bán",
    "KQKD quý hiện tại",
    "KQKD quý cùng kỳ",
    "Điểm",
)


def _blank(symbol: str, industry: str) -> dict[str, object]:
    row = {name: "—" for name in _COLUMNS}
    row["Ngành"] = industry
    row["Mã"] = symbol
    row["Điểm"] = None
    return row


def load_industries() -> dict[str, str]:
    """Mã → tên ngành từ file ICB đã lưu. Không có file thì trả rỗng."""
    if not INDUSTRY_PATH.exists():
        return {}
    try:
        table = pd.read_csv(INDUSTRY_PATH)
    except Exception:
        return {}
    if "symbol" not in table.columns or "icb_name" not in table.columns:
        return {}
    symbols = table["symbol"].astype(str).str.upper()
    names = table["icb_name"].astype(str)
    return {symbol: name for symbol, name in zip(symbols, names) if symbol and name}


def _direction(latest: float, earlier: float) -> str:
    if earlier == 0 or math.isnan(latest) or math.isnan(earlier):
        return "—"
    if latest > earlier:
        return "Tăng"
    if latest < earlier:
        return "Giảm"
    return "Đi ngang"


def _price_strength(close: pd.Series, volume: pd.Series) -> tuple[float | None, float | None]:
    """Lợi suất 20 phiên (%) và KL TB 10 phiên. Thiếu dữ liệu thì None."""
    if len(close) <= _RETURN_BARS or pd.isna(close.iloc[-1]) or pd.isna(close.iloc[-1 - _RETURN_BARS]):
        strength = None
    else:
        base = float(close.iloc[-1 - _RETURN_BARS])
        strength = None if base == 0 else (float(close.iloc[-1]) / base - 1) * 100
    window = volume.dropna().tail(10)
    average = float(window.mean()) if len(window) >= 10 and float(window.mean()) > 0 else None
    return strength, average


def _percentile(values: list[float | None]) -> list[float]:
    known = sorted(value for value in values if value is not None)
    if not known:
        return [0.0 for _ in values]

    def place(value: float | None) -> float:
        if value is None:
            return 0.0
        below = sum(item < value for item in known)
        equal = sum(item == value for item in known)
        return (below + 0.5 * equal) / len(known)

    return [place(value) for value in values]


def _indicator_text(symbol: str, frame: pd.DataFrame, row: dict[str, object]) -> None:
    close = pd.to_numeric(frame["close"], errors="coerce")
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    price = float(close.iloc[-1])
    if len(close) >= 2:
        row["Xu hướng ngày"] = _direction(price, float(close.iloc[-2]))
    if len(close) > _WEEK_BARS:
        row["Xu hướng tuần"] = _direction(price, float(close.iloc[-1 - _WEEK_BARS]))
    if len(close) > _MONTH_BARS:
        row["Xu hướng tháng"] = _direction(price, float(close.iloc[-1 - _MONTH_BARS]))
    try:
        pattern = candle_pattern(frame)
    except Exception:
        pattern = None
    if pattern:
        row["Tín hiệu nến"] = pattern
    try:
        lower, _mid, upper = bollinger(close)
        if pd.notna(lower.iloc[-1]) and pd.notna(upper.iloc[-1]):
            if price >= float(upper.iloc[-1]):
                row["BB"] = "Trên dải"
            elif price <= float(lower.iloc[-1]):
                row["BB"] = "Dưới dải"
            else:
                row["BB"] = "Trong dải"
    except Exception:
        pass
    try:
        fast = sma(close, 20)
        slow = sma(close, 50)
        if pd.notna(fast.iloc[-1]):
            above_fast = price >= float(fast.iloc[-1])
            if pd.notna(slow.iloc[-1]) and above_fast and float(fast.iloc[-1]) >= float(slow.iloc[-1]):
                row["MA"] = "Tăng"
            elif pd.notna(slow.iloc[-1]) and not above_fast and float(fast.iloc[-1]) <= float(slow.iloc[-1]):
                row["MA"] = "Giảm"
            else:
                row["MA"] = "Trên MA20" if above_fast else "Dưới MA20"
    except Exception:
        pass
    rsi_now = None
    try:
        series = rsi(close)
        if pd.notna(series.iloc[-1]):
            rsi_now = float(series.iloc[-1])
            row["RSI"] = f"{rsi_now:.1f}"
    except Exception:
        pass
    hist_now = None
    try:
        _line, _signal, hist = macd(close)
        if pd.notna(hist.iloc[-1]):
            hist_now = float(hist.iloc[-1])
            row["MACD"] = "Dương" if hist_now > 0 else "Âm" if hist_now < 0 else "0"
    except Exception:
        pass
    try:
        _tenkan, _kijun, cloud_a, cloud_b = ichimoku(high, low)
        if pd.notna(cloud_a.iloc[-1]) and pd.notna(cloud_b.iloc[-1]):
            top = max(float(cloud_a.iloc[-1]), float(cloud_b.iloc[-1]))
            bottom = min(float(cloud_a.iloc[-1]), float(cloud_b.iloc[-1]))
            if price > top:
                row["Mây"] = "Trên mây"
            elif price < bottom:
                row["Mây"] = "Dưới mây"
            else:
                row["Mây"] = "Trong mây"
    except Exception:
        pass
    try:
        banker, _hot, _raw = mcdx(close)
        if pd.notna(banker.iloc[-1]):
            row["MCDX"] = f"{float(banker.iloc[-1]):.1f}"
    except Exception:
        pass
    row["_rsi"] = rsi_now
    row["_hist"] = hist_now


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _strength_label(score: float | None, rsi_now: float | None, hist_now: float | None) -> str:
    if score is None:
        return "—"
    bullish = (rsi_now is not None and rsi_now >= 50) or (hist_now is not None and hist_now > 0)
    bearish = (rsi_now is not None and rsi_now < 50) or (hist_now is not None and hist_now < 0)
    if score >= 50 and bullish:
        side = "Mua"
    elif score < 50 and bearish:
        side = "Bán"
    else:
        side = "Trung tính"
    return f"{side} {score:.0f}"


def build_industry_top(universe: list[str] | None = None) -> pd.DataFrame:
    """Mỗi ngành lấy tối đa 5 mã điểm cao nhất trong universe.

    Điểm = 70% thứ hạng sức mạnh giá 20 phiên + 30% thứ hạng KL TB 10 phiên, trong chính ngành đó.
    """
    industries = load_industries()
    symbols = [item.strip().upper() for item in (universe if universe is not None else UNIVERSE)]
    grouped: dict[str, list[dict[str, object]]] = {}
    for symbol in symbols:
        industry = industries.get(symbol)
        if not industry:
            continue
        frame = load_symbol_csv(BARS_DIR, symbol)
        row = _blank(symbol, industry)
        strength = None
        liquidity = None
        if frame is not None and not frame.empty and "close" in frame.columns:
            try:
                _indicator_text(symbol, frame, row)
                close = pd.to_numeric(frame["close"], errors="coerce")
                volume = pd.to_numeric(frame.get("volume", pd.Series(dtype=float)), errors="coerce")
                strength, liquidity = _price_strength(close, volume)
            except Exception:
                strength, liquidity = None, None
        row["_strength"] = strength
        row["_liquidity"] = liquidity
        try:
            current, prior = kqkd_cells(symbol)
            row["KQKD quý hiện tại"] = current
            row["KQKD quý cùng kỳ"] = prior
        except Exception:
            row["KQKD quý hiện tại"] = "—"
            row["KQKD quý cùng kỳ"] = "—"
        grouped.setdefault(industry, []).append(row)

    chosen: list[dict[str, object]] = []
    for rows in grouped.values():
        returns = _percentile([row["_strength"] for row in rows])  # type: ignore[arg-type]
        volumes = _percentile([row["_liquidity"] for row in rows])  # type: ignore[arg-type]
        for row, ret_rank, vol_rank in zip(rows, returns, volumes):
            if row["_strength"] is None and row["_liquidity"] is None:
                row["Điểm"] = None
            else:
                row["Điểm"] = round(70 * ret_rank + 30 * vol_rank, 1)
            row["Cường độ mua/bán"] = _strength_label(
                _as_float(row["Điểm"]),
                _as_float(row.get("_rsi")),
                _as_float(row.get("_hist")),
            )
        ranked = sorted(rows, key=lambda item: (item["Điểm"] is not None, item["Điểm"] or -1), reverse=True)
        chosen.extend(ranked[:TOP_PER_INDUSTRY])
    if not chosen:
        return pd.DataFrame(columns=list(_COLUMNS))
    board = pd.DataFrame(chosen)
    return board[list(_COLUMNS)].sort_values(["Ngành", "Điểm"], ascending=[True, False], na_position="last")


def show_industry_top() -> None:
    st.caption(
        "Mỗi ngành lấy tối đa 5 mã trong danh sách quét. "
        "Điểm = 70% thứ hạng sức mạnh giá 20 phiên + 30% thứ hạng khối lượng trung bình 10 phiên, so trong ngành. "
        "Nến lấy từ dữ liệu đã lưu. KQKD = lợi nhuận sau thuế (LNST) quý hiện tại và cùng kỳ năm trước. Thiếu dữ liệu thì «—»."
    )
    try:
        board = build_industry_top()
    except Exception as error:
        st.error(f"Không lập được Top 5 mỗi ngành: {error}")
        return
    if board.empty:
        st.info("Chưa có mã nào vừa thuộc universe vừa có ngành trong file ICB.")
        return
    for industry, part in board.groupby("Ngành", sort=True):
        st.markdown(f"**{industry}** · {len(part)} mã")
        shown = part.drop(columns=["Ngành"])
        render_data_table(
            shown,
            variant="analytical",
            pin="Mã",
            key_cols=["Điểm", "Cường độ mua/bán", "Xu hướng ngày", "KQKD quý hiện tại"],
            key=f"top5_{industry}",
            alt=f"Top mã ngành {industry}",
        )
        from ui.trading_desk import offer_to_desk

        for _, item in part.iterrows():
            label, action = st.columns([5, 2])
            label.write(str(item["Mã"]))
            with action:
                offer_to_desk(str(item["Mã"]), str(industry), f"to_desk_{industry}_{item['Mã']}")
