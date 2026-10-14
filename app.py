"""Quét thị trường kiểu YSradar. Trang mở chỉ đọc top20_cache.csv."""

from __future__ import annotations

import math
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_ta  # đăng ký df.ta
import plotly.graph_objects as go
import streamlit as st
from khuyen_nghi import PORTFOLIO
from vnstock import Fundamental, Market, Reference

# Cảnh báo phân quyền của vnstock là UserWarning. Trang này không gọi báo cáo đầy đủ.
warnings.filterwarnings("ignore", category=UserWarning, module=r"vnstock(\.|$)")

from config import (
    BARS_DIR, BB_LENGTH, BB_STD, CACHE_PATH, CHART_DAYS, COLUMNS, EPS_DIR, HN_ZONE,
    INDUSTRY_LEVEL, INDUSTRY_PATH, MARKET_INDEX, MIN_AVG_VOLUME, MIN_ROE, SCAN_DAYS,
    SUPPORT_BAND, SUPPORT_DAYS, THOUSAND_VND, TOP_N, UNIVERSE, VALUATION_PATH, WORKERS,
)
import canslim
import charts
import config
import indicators
import patterns


def _quota_hit(error: Exception) -> bool:
    text = str(error).lower()
    return "hạn mức" in text or "quota" in text or "per-minute" in text


def _call(action):
    """Gọi API. Golden cho 500 lượt/phút nên không nghỉ giữa các lần. Hết hạn mức thì chờ rồi thử lại."""
    for attempt in range(6):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                return action()
        except Exception as error:
            if _quota_hit(error) and attempt < 5:
                time.sleep(20)
                continue
            raise
    raise RuntimeError("Hết số lần thử sau khi chạm hạn mức.")


def _as_ratio(value: float) -> float:
    """12,5 và 0,125 đều về dạng tỷ lệ."""
    return value / 100 if abs(value) > 1.5 else value


def _day_index(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.sort_values("time").copy()
    stamps = pd.to_datetime(work["time"])
    if getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert("Asia/Ho_Chi_Minh")
    work["_day"] = stamps.dt.date
    return work


def ratio_quarterly(fundamental: Fundamental, ticker: str) -> pd.DataFrame:
    """Chỉ số quý. vnstock 5 chưa có ratio_quarterly, nên gọi ratio(period='quarter')."""
    equity = fundamental.equity(ticker)
    method = getattr(equity, "ratio_quarterly", None)
    if callable(method):
        return method()
    return equity.ratio(period="quarter")


def _latest_metric(frame: pd.DataFrame, item_id: str) -> float | None:
    """Giá trị kỳ mới nhất của một mã chỉ số. Thiếu dữ liệu thì trả None, không điền 0."""
    if frame.empty or "id" not in frame.columns or "value" not in frame.columns:
        return None
    matched = frame.loc[frame["id"].astype(str).str.fullmatch(item_id, case=False)]
    if matched.empty:
        return None
    ordered = matched.assign(_period=matched["period"].astype(str)).sort_values("_period")
    value = pd.to_numeric(ordered["value"], errors="coerce").iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def _latest_roe(frame: pd.DataFrame) -> float:
    """ROE quý mới nhất. vnstock 5 đặt mã RT_PRT_ROE, giá trị thường đã là tỷ lệ."""
    if frame.empty:
        raise ValueError("bảng chỉ số trống")
    if "id" in frame.columns and "value" in frame.columns:
        ids = frame["id"].astype(str)
        matched = frame.loc[ids.str.fullmatch(r"RT_PRT_ROE|ROE|ROEA|ROE_TTM", case=False)]
        if matched.empty and "name" in frame.columns:
            matched = frame.loc[frame["name"].astype(str).str.contains(r"\bROE\b", case=False, na=False)]
        if matched.empty:
            raise ValueError("không thấy ROE trong chỉ số quý")
        matched = matched.assign(_period=matched["period"].astype(str)).sort_values("_period")
        return _as_ratio(float(matched["value"].iloc[-1]))
    roe_columns = [column for column in frame.columns if "roe" in str(column).lower()]
    if not roe_columns:
        raise ValueError("không thấy cột ROE")
    series = frame[roe_columns[0]].dropna()
    if series.empty:
        raise ValueError("ROE trống")
    return _as_ratio(float(series.iloc[-1]))


def _ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Nến ngày từ KBS. Cùng giá đóng cửa với VCI, trả về nhanh hơn trên gói Golden."""
    return _call(
        lambda: Market().equity(symbol).ohlcv(
            start=start,
            end=end,
            interval="1D",
            source="kbs",
        )
    )


def _fresh_bars(path: Path, start: str) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or "time" not in frame.columns:
        return None
    stamps = pd.to_datetime(frame["time"])
    newest = stamps.max()
    oldest = stamps.min()
    if pd.isna(newest) or pd.isna(oldest):
        return None
    if newest.date() < date.today() - timedelta(days=4):
        return None
    if oldest.date().isoformat() > start:
        return None
    return frame


def _save_bars(symbol: str, frame: pd.DataFrame) -> None:
    BARS_DIR.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["_day"], errors="ignore").to_csv(BARS_DIR / f"{symbol}.csv", index=False)


def _price_stats(bars: pd.DataFrame) -> tuple[float, float, float]:
    if len(bars) < 20:
        raise ValueError("chưa đủ 20 phiên")
    anchor = bars["_day"].iloc[-1] - timedelta(days=91)
    history = bars.loc[bars["_day"] <= anchor]
    base = float(history["close"].iloc[-1] if not history.empty else bars["close"].iloc[0])
    last = float(bars["close"].iloc[-1])
    if base == 0:
        raise ValueError("giá nền bằng 0")
    strength = round((last / base - 1) * 100, 2)
    volume = round(float(bars["volume"].tail(20).mean()), 0)
    return last, strength, volume


def _scan_one(
    symbol: str, start: str, end: str
) -> tuple[dict[str, object] | None, str | None, dict[str, object] | None]:
    try:
        bars = _day_index(_ohlcv(symbol, start, end))
        _save_bars(symbol, bars)
        price, strength, volume = _price_stats(bars)
        ratios = _call(lambda: ratio_quarterly(Fundamental(), symbol))
        roe = _latest_roe(ratios)
        quote = {
            "Mã": symbol,
            "P/E": _latest_metric(ratios, "RT_VALUE_PE"),
            "P/B": _latest_metric(ratios, "RT_VALUE_PB"),
            "ROE": roe,
        }
    except Exception as error:
        return None, f"{symbol}: {error}", None
    if volume < MIN_AVG_VOLUME or roe < MIN_ROE:
        return None, None, quote
    return (
        {
            "Mã": symbol,
            "Giá": price,
            "RS 3 tháng (%)": strength,
            "ROE (%)": round(roe * 100, 2),
            "KLGD TB 20 phiên": volume,
        },
        None,
        quote,
    )


def _store_valuation(quotes: list[dict[str, object]]) -> None:
    if not quotes:
        return
    fresh = pd.DataFrame(quotes)
    if VALUATION_PATH.exists():
        previous = pd.read_csv(VALUATION_PATH)
        fresh = pd.concat([previous, fresh], ignore_index=True)
    fresh = fresh.drop_duplicates("Mã", keep="last")
    VALUATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    fresh.to_csv(VALUATION_PATH, index=False)


def scan_top20() -> tuple[pd.DataFrame, list[str]]:
    """Quét khi bấm nút. Giá và ROE của các mã chạy song song."""
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    quotes: list[dict[str, object]] = []
    start = (date.today() - timedelta(days=SCAN_DAYS)).isoformat()
    end = date.today().isoformat()
    progress = st.progress(0, text="Đang quét...")
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_scan_one, symbol, start, end) for symbol in UNIVERSE]
        for index, future in enumerate(as_completed(futures), start=1):
            progress.progress(index / len(UNIVERSE), text=f"Đã xong {index}/{len(UNIVERSE)}")
            row, error, quote = future.result()
            if error:
                errors.append(error)
            elif row is not None:
                rows.append(row)
            if quote is not None:
                quotes.append(quote)
    progress.empty()
    _store_valuation(quotes)
    if not rows:
        return pd.DataFrame(columns=COLUMNS), errors
    board = pd.DataFrame(rows).sort_values("RS 3 tháng (%)", ascending=False).head(TOP_N)
    return board[COLUMNS].reset_index(drop=True), errors


def read_cache() -> pd.DataFrame:
    if not CACHE_PATH.exists():
        return pd.DataFrame(columns=COLUMNS)
    board = pd.read_csv(CACHE_PATH)
    missing = [column for column in COLUMNS if column not in board.columns]
    if missing:
        raise ValueError(f"thiếu cột {', '.join(missing)}")
    return board[COLUMNS]


def load_bars(symbol: str, start: str) -> pd.DataFrame:
    cached = _fresh_bars(BARS_DIR / f"{symbol}.csv", start)
    if cached is not None:
        return _day_index(cached)
    frame = _ohlcv(symbol, start, date.today().isoformat())
    _save_bars(symbol, frame)
    return _day_index(frame)


def style_board(board: pd.DataFrame):
    def paint(value: object) -> str:
        if pd.isna(value):
            return ""
        number = float(value)
        if number > 0:
            return "color: #3ddc97"
        if number < 0:
            return "color: #ff6b6b"
        return ""

    return board.style.format(
        {
            "Giá": "{:.2f}",
            "RS 3 tháng (%)": "{:+.2f}",
            "ROE (%)": "{:.2f}",
            "KLGD TB 20 phiên": "{:,.0f}",
        }
    ).map(paint, subset=["RS 3 tháng (%)", "ROE (%)"])


def _bollinger(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger (20, 2) trên chuỗi giá đã có. Độ lệch chuẩn tổng thể, không gọi mạng."""
    middle = close.rolling(BB_LENGTH, min_periods=BB_LENGTH).mean()
    sigma = close.rolling(BB_LENGTH, min_periods=BB_LENGTH).std(ddof=0)
    upper = middle + BB_STD * sigma
    lower = middle - BB_STD * sigma
    return lower, middle, upper


def _line(values: pd.Series) -> list[float | None]:
    return [None if pd.isna(value) else float(value) for value in values]


def show_charts(symbol: str, bars: pd.DataFrame, neckline: float | None) -> None:
    """Đồ thị nến chính, bên dưới là các tab con cho từng chỉ báo."""
    w = indicators.enrich(bars)
    st.plotly_chart(charts.candle_chart(symbol, w, neckline), width="stretch", theme=None,
                    alt=f"Nến ngày, MA20/MA50, Bollinger và đáy trung tâm của {symbol}")
    with st.expander("Chỉ báo: khối lượng, RSI, MACD, MFI", expanded=True):
        for tab, (name, builder) in zip(st.tabs(list(charts.INDICATOR_CHARTS)), charts.INDICATOR_CHARTS.items()):
            with tab:
                st.plotly_chart(builder(symbol, w), width="stretch", theme=None, alt=f"{name} của {symbol}")


def show_money_flow(symbol: str, bars: pd.DataFrame) -> None:
    """Bảng dòng tiền & chỉ báo phiên cuối, kèm diễn giải ngắn."""
    st.subheader("Dòng tiền & chỉ báo")
    w = indicators.enrich(bars)
    m = indicators.money_flow_summary(w)
    cols = st.columns(5)
    cols[0].metric(f"RSI({config.RSI_LENGTH})", f"{m['rsi']:.1f}")
    cols[1].metric(f"MFI({config.MFI_LENGTH})", f"{m['mfi']:.1f}")
    cols[2].metric("MACD hist", f"{m['macd_hist']:+.2f}")
    cols[3].metric("KL / TB20", f"{m['vol_ratio']:.2f}×")
    cols[4].metric("OBV 20 phiên", "Tăng" if m["obv_up"] else "Giảm")
    notes = []
    if m["rsi"] >= config.RSI_OVERBOUGHT:
        notes.append("RSI vùng quá mua")
    elif m["rsi"] <= config.RSI_OVERSOLD:
        notes.append("RSI vùng quá bán")
    notes.append("MACD trên signal (động lượng tăng)" if m["macd"] > m["macd_signal"] else "MACD dưới signal (động lượng yếu)")
    if m["mfi"] >= 80:
        notes.append("MFI > 80: tiền vào nóng")
    elif m["mfi"] <= 20:
        notes.append("MFI < 20: tiền rút mạnh")
    notes.append("OBV đi lên: dòng tiền tích luỹ" if m["obv_up"] else "OBV đi xuống: dòng tiền phân phối")
    if m["vol_ratio"] >= 1.5:
        notes.append("khối lượng đột biến")
    st.caption(f"{symbol}: " + "; ".join(notes) + ".")


def show_patterns(symbol: str, bars: pd.DataFrame) -> None:
    st.subheader("Mẫu hình kỹ thuật (heuristic)")
    rows = [
        {"Mẫu hình": r["name"], "Khớp": "✓" if r["found"] else "—", "Chi tiết": r["detail"]}
        for r in patterns.detect_all(bars)
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 alt=f"Mẫu hình giá nhận diện tự động cho {symbol}")
    st.caption("Nhận diện bằng quy tắc đơn giản trên nến ngày (ngưỡng trong config.PATTERNS). "
               "Chỉ là gợi ý, luôn kiểm tra lại bằng mắt trên đồ thị.")


def commentary(symbol: str, frame: pd.DataFrame) -> None:
    work = indicators.enrich(frame)
    price = float(work["close"].iloc[-1])
    ma20 = float(work["MA20"].iloc[-1])
    window = work.tail(20)
    support = float(window["low"].min())
    resistance = float(window["high"].max())
    if price > ma20:
        st.success(
            f"{symbol} đóng cửa {price:.2f}, cao hơn MA20 {ma20:.2f} "
            f"({(price / ma20 - 1) * 100:+.1f}%). Trạng thái ngắn hạn: Tăng."
        )
    elif price < ma20:
        st.warning(
            f"{symbol} đóng cửa {price:.2f}, thấp hơn MA20 {ma20:.2f} "
            f"({(price / ma20 - 1) * 100:+.1f}%). Trạng thái ngắn hạn: Giảm."
        )
    else:
        st.info(f"{symbol} đóng cửa đúng MA20 {ma20:.2f}.")
    above_support = (price / support - 1) * 100 if support else 0
    below_resistance = (resistance / price - 1) * 100 if price else 0
    st.write(
        f"Hỗ trợ 20 phiên {support:.2f}, giá đang cách {above_support:.1f}%. "
        f"Kháng cự 20 phiên {resistance:.2f}, giá đang cách {below_resistance:.1f}%."
    )


def _industry_table() -> pd.DataFrame:
    if INDUSTRY_PATH.exists():
        age = date.today() - date.fromtimestamp(INDUSTRY_PATH.stat().st_mtime)
        if age <= timedelta(days=7):
            return pd.read_csv(INDUSTRY_PATH)
    listed = _call(lambda: Reference().equity.list_by_industry())
    level = pd.to_numeric(listed["icb_level"], errors="coerce")
    chosen = listed.loc[level == INDUSTRY_LEVEL, ["symbol", "icb_name"]].copy()
    chosen["symbol"] = chosen["symbol"].astype(str).str.upper()
    chosen = chosen.drop_duplicates("symbol")
    INDUSTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(INDUSTRY_PATH, index=False)
    return chosen


def _read_valuation() -> pd.DataFrame:
    if not VALUATION_PATH.exists():
        return pd.DataFrame(columns=["Mã", "P/E", "P/B"])
    stored = pd.read_csv(VALUATION_PATH)
    for column in ("Mã", "P/E", "P/B"):
        if column not in stored.columns:
            stored[column] = pd.NA
    return stored


def _multiples(symbol: str) -> dict[str, object]:
    try:
        ratios = _call(lambda: ratio_quarterly(Fundamental(), symbol))
    except Exception:
        return {"Mã": symbol, "P/E": None, "P/B": None}
    return {
        "Mã": symbol,
        "P/E": _latest_metric(ratios, "RT_VALUE_PE"),
        "P/B": _latest_metric(ratios, "RT_VALUE_PB"),
    }


def valuation_board(symbol: str) -> tuple[pd.DataFrame, str, float | None, float | None]:
    """P/E, P/B của mã và trung vị các mã cùng ngành ICB cấp 3 trong danh sách quét."""
    industries = _industry_table()
    names = industries.set_index("symbol")["icb_name"]
    industry = names.get(symbol)
    if industry is None or (isinstance(industry, float) and pd.isna(industry)):
        raise ValueError("không thấy nhóm ngành")
    peers = [item for item in UNIVERSE if names.get(item) == industry]
    if symbol not in peers:
        peers = [symbol, *peers]
    stored = _read_valuation().set_index("Mã")
    missing = [item for item in peers if item not in stored.index]
    fetched: list[dict[str, object]] = []
    if missing:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            fetched.extend(pool.map(_multiples, missing))
        _store_valuation(fetched)
        stored = _read_valuation().set_index("Mã")
    records: list[dict[str, object]] = []
    for item in peers:
        if item in stored.index:
            row = stored.loc[item]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            pe = pd.to_numeric(row["P/E"], errors="coerce")
            pb = pd.to_numeric(row["P/B"], errors="coerce")
        else:
            pe = pd.NA
            pb = pd.NA
        records.append(
            {
                "Mã": item,
                "Vai trò": "Mã đang chọn" if item == symbol else "Đối thủ",
                "P/E": None if pd.isna(pe) else float(pe),
                "P/B": None if pd.isna(pb) else float(pb),
            }
        )
    board = pd.DataFrame(records)
    rivals = board.loc[board["Mã"] != symbol, "P/E"]
    rival_pb = board.loc[board["Mã"] != symbol, "P/B"]
    pe_median = float(rivals.median()) if rivals.notna().any() else None
    pb_median = float(rival_pb.median()) if rival_pb.notna().any() else None
    return board, str(industry), pe_median, pb_median


def show_valuation(symbol: str) -> None:
    st.subheader("Định giá so với ngành")
    try:
        board, industry, pe_median, pb_median = valuation_board(symbol)
    except Exception as error:
        st.warning(f"Không lập được ma trận định giá của {symbol}: {error}")
        return
    st.caption(f"Nhóm ngành ICB cấp 3: {industry}. Trung vị tính trên các mã đối thủ trong danh sách quét.")
    summary = pd.DataFrame(
        [
            {
                "Mã": "Trung vị đối thủ",
                "Vai trò": industry,
                "P/E": pe_median,
                "P/B": pb_median,
            }
        ]
    )
    shown = pd.concat([board, summary], ignore_index=True)
    st.dataframe(
        shown.style.format({"P/E": "{:.2f}", "P/B": "{:.2f}"}, na_rep="—"),
        hide_index=True,
        width="stretch",
        alt=f"P/E và P/B của {symbol} so với trung vị các mã cùng ngành trong danh sách quét",
    )
    own = board.loc[board["Mã"] == symbol, "P/E"]
    own_pe = float(own.iloc[0]) if not own.empty and pd.notna(own.iloc[0]) else None
    if own_pe is None or pe_median is None:
        st.info(f"{symbol} chưa đủ P/E của mã hoặc của đối thủ để so trung vị.")
    elif own_pe < pe_median:
        st.success("✓ Định giá hấp dẫn: P/E thấp hơn trung vị ngành.")
    else:
        st.warning(f"P/E của {symbol} không thấp hơn trung vị ngành.")


def market_session(moment: datetime | None = None) -> tuple[str, str]:
    """Sáng 9:00–11:30 và chiều 13:00–14:45 theo giờ Hà Nội. Cuối tuần là ngoài phiên."""
    current = moment or datetime.now(HN_ZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=HN_ZONE)
    else:
        current = current.astimezone(HN_ZONE)
    clock = current.strftime("%H:%M %d/%m/%Y")
    if current.weekday() >= 5:
        return "Ngoài phiên", clock
    minute = current.hour * 60 + current.minute
    morning = 9 * 60 <= minute <= 11 * 60 + 30
    afternoon = 13 * 60 <= minute <= 14 * 60 + 45
    return ("Trong phiên" if morning or afternoon else "Ngoài phiên"), clock


def support_scan(bars: pd.DataFrame) -> dict[str, object]:
    """Đáy 6 tháng, số lần chạm vùng 1,5% rồi bật lên, và đáy trung tâm giữa các lần chạm."""
    work = bars.copy()
    for column in ("high", "low", "close"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    cutoff = date.today() - timedelta(days=SUPPORT_DAYS)
    window = work.loc[work["_day"] >= cutoff].reset_index(drop=True)
    if len(window) < 20:
        window = work.reset_index(drop=True)
    if window["low"].dropna().empty or len(window) < 2:
        raise ValueError("chưa đủ phiên để quét đáy")
    support = float(window["low"].min())
    if support <= 0:
        raise ValueError("đáy không hợp lệ")
    zone_top = support * (1 + SUPPORT_BAND)
    flags = (window["low"].fillna(zone_top * 10) <= zone_top).fillna(False).to_numpy()
    closes = window["close"].fillna(0).to_numpy(dtype=float)
    highs = window["high"].fillna(0).to_numpy(dtype=float)
    count = len(window)
    tests = 0
    touch_at = [index for index, flag in enumerate(flags) if flag]
    cursor = 0
    while cursor < count:
        if not flags[cursor]:
            cursor += 1
            continue
        while cursor < count and flags[cursor]:
            cursor += 1
        bounced = cursor < count and bool((closes[cursor:] > zone_top).any())
        if bounced or cursor >= count:
            tests += 1
    if len(touch_at) >= 2:
        between = [highs[index] for index in range(touch_at[0], touch_at[-1]) if not flags[index] and highs[index] > 0]
        neckline = float(max(between)) if between else float(max(highs[touch_at[0] : touch_at[-1] + 1]))
    else:
        low_at = int(window["low"].idxmin())
        segment = [highs[index] for index in range(low_at + 1, count) if highs[index] > 0]
        neckline = float(max(segment)) if segment else float(highs[low_at])
    price = float(closes[-1])
    previous = float(closes[-2])
    return {
        "support": support,
        "zone_top": zone_top,
        "tests": tests,
        "in_zone": price <= zone_top,
        "neckline": neckline,
        "crossed": previous <= neckline < price,
        "price": price,
    }


def show_support(report: dict[str, object]) -> None:
    if report["in_zone"]:
        st.warning(
            "⚠️ Hệ thống: Cổ phiếu đang test hỗ trợ cứng lần thứ "
            f"{report['tests']} -> Vùng hấp dẫn dò đường theo Mentor."
        )
    if report["crossed"]:
        st.success("🚨 XÁC NHẬN ĐẢO CHIỀU: Giá vượt đáy trung tâm, giải ngân hết số tiền còn lại!")
    st.caption(
        f"Đáy 6 tháng {float(report['support']):.2f}. "
        f"Vùng chạm tới {float(report['zone_top']):.2f}. "
        f"Đáy trung tâm {float(report['neckline']):.2f}."
    )


def _body_parts(row: pd.Series) -> tuple[float, float, float, float]:
    open_ = float(row["open"])
    close = float(row["close"])
    high = float(row["high"])
    low = float(row["low"])
    span = high - low
    body = abs(close - open_)
    upper = high - max(open_, close)
    lower = min(open_, close) - low
    return span, body, upper, lower


def candle_pattern(bars: pd.DataFrame) -> str | None:
    """Mẫu hình của phiên cuối: Engulfing, Hammer, Shooting Star hoặc Doji."""
    work = bars[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").fillna(0)
    if len(work) < 2:
        return None
    last = work.iloc[-1]
    previous = work.iloc[-2]
    span, body, upper, lower = _body_parts(last)
    if span <= 0:
        return None
    prev_open = float(previous["open"])
    prev_close = float(previous["close"])
    open_ = float(last["open"])
    close = float(last["close"])
    bullish = close > open_ and prev_close < prev_open and open_ <= prev_close and close >= prev_open
    bearish = close < open_ and prev_close > prev_open and open_ >= prev_close and close <= prev_open
    if bullish and body > 0:
        return "Engulfing tăng"
    if bearish and body > 0:
        return "Engulfing giảm"
    if body > 0 and lower >= body * 2 and upper <= body and lower > upper:
        return "Hammer"
    if body > 0 and upper >= body * 2 and lower <= body and upper > lower:
        return "Shooting Star"
    if body <= span * 0.1:
        return "Doji"
    return None


def explain_pattern(name: str) -> str:
    notes = {
        "Doji": (
            "Theo John J. Murphy và Steve Nison, Doji thể hiện sự lưỡng lự tuyệt đối của thị trường, "
            "cung cầu cân bằng, cần đợi nến ngày tiếp theo để xác nhận xu hướng."
        ),
        "Hammer": (
            "Theo Steve Nison, Hammer là nến có bóng dưới dài và thân nhỏ phía trên: "
            "phe bán đã bị đẩy lùi trong phiên. Tín hiệu tăng cần nến sau xác nhận."
        ),
        "Shooting Star": (
            "Theo Steve Nison, Shooting Star là nến có bóng trên dài và thân nhỏ phía dưới: "
            "giá bị từ chối ở vùng cao. Tín hiệu giảm cần nến sau xác nhận."
        ),
        "Engulfing tăng": (
            "Theo John J. Murphy, nến nhấn chìm tăng là thân xanh phủ kín thân đỏ phía trước, "
            "phe mua giành lại quyền kiểm soát."
        ),
        "Engulfing giảm": (
            "Theo John J. Murphy, nến nhấn chìm giảm là thân đỏ phủ kín thân xanh phía trước, "
            "phe bán giành lại quyền kiểm soát."
        ),
    }
    return notes[name]


def show_candle_lesson(symbol: str, bars: pd.DataFrame) -> None:
    st.subheader("Đọc vị nến phiên gần nhất")
    try:
        name = candle_pattern(bars)
    except Exception as error:
        st.warning(f"Không đọc được nến của {symbol}: {error}")
        return
    if name is None:
        st.info(f"{symbol} chưa khớp Doji, Hammer, Shooting Star hay Engulfing ở phiên cuối.")
        return
    st.info(f"{symbol}: {name}. {explain_pattern(name)}")


def _basic_eps(symbol: str) -> pd.DataFrame:
    path = EPS_DIR / f"{symbol}.csv"
    if path.exists() and date.fromtimestamp(path.stat().st_mtime) == date.today():
        return pd.read_csv(path)
    statement = _call(lambda: Fundamental().equity(symbol).income_statement(period="quarter"))
    rows = statement.loc[
        statement["id"].astype(str) == "IS_BASIC_EARNINGS_PER_SHARE",
        ["period", "value"],
    ].copy()
    EPS_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False)
    return rows


def _eps_growth(symbol: str) -> tuple[str, float] | None:
    series = _basic_eps(symbol)
    series = series.assign(
        period=series["period"].astype(str),
        value=pd.to_numeric(series["value"], errors="coerce"),
    ).dropna(subset=["value"])
    series = series.sort_values("period")
    if series.empty:
        return None
    latest = series.iloc[-1]
    period = str(latest["period"])
    if "-Q" not in period:
        return None
    year, quarter = period.split("-Q", maxsplit=1)
    prior = f"{int(year) - 1}-Q{quarter}"
    older = series.loc[series["period"] == prior, "value"]
    if older.empty:
        return None
    base = float(older.iloc[-1])
    if base == 0:
        return None
    growth = (float(latest["value"]) - base) / abs(base)
    return period, growth


def _stored_roe(symbol: str) -> float | None:
    stored = _read_valuation()
    if "ROE" not in stored.columns or stored.empty:
        return None
    matched = stored.loc[stored["Mã"].astype(str).str.upper() == symbol, "ROE"]
    if matched.empty:
        return None
    value = pd.to_numeric(matched, errors="coerce").iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def load_index_bars() -> pd.DataFrame | None:
    """Nến VNINDEX cho chữ M và so sánh RS. Lỗi hoặc không có dữ liệu thì trả None."""
    start = (date.today() - timedelta(days=CHART_DAYS)).isoformat()
    path = BARS_DIR / f"{MARKET_INDEX}.csv"
    cached = _fresh_bars(path, start)
    if cached is not None:
        return _day_index(cached)
    end = date.today().isoformat()
    attempts = [
        lambda: Market().index(MARKET_INDEX).ohlcv(start=start, end=end, interval="1D"),
        lambda: Market().equity(MARKET_INDEX).ohlcv(start=start, end=end, interval="1D", source="kbs"),
        lambda: Market().equity(MARKET_INDEX).ohlcv(start=start, end=end, interval="1D"),
    ]
    for attempt in attempts:
        try:
            frame = _call(attempt)
            if frame is not None and not frame.empty and "close" in frame.columns:
                _save_bars(MARKET_INDEX, frame)
                return _day_index(frame)
        except Exception:
            continue
    return None


def show_canslim(symbol: str, bars: pd.DataFrame) -> None:
    st.subheader("CANSLIM — checklist 7 chữ")
    growth = None
    period = "—"
    roe = None
    try:
        found = _eps_growth(symbol)
        if found is not None:
            period, growth = found
    except Exception:
        growth = None
    try:
        roe = _stored_roe(symbol)
        if roe is None:
            ratios = _call(lambda: ratio_quarterly(Fundamental(), symbol))
            roe = _latest_roe(ratios)
    except Exception:
        roe = None
    index_bars = load_index_bars()
    index_ret = canslim.return_3m(index_bars) if index_bars is not None else None
    peers = canslim.universe_returns()
    rows = [
        canslim.check_c(None if growth is None else growth * 100, period),
        canslim.check_a(None if roe is None else roe * 100),
        canslim.check_n(bars),
        canslim.check_s(bars),
        canslim.check_l(canslim.return_3m(bars), peers, index_ret),
        canslim.check_i(),
        canslim.check_m(index_bars),
    ]
    passed, rated = canslim.score(rows)
    st.metric("Điểm CANSLIM", f"{passed}/{rated}", help="Chỉ tính các chữ có dữ liệu (bỏ N/A).")

    def paint_mark(value: object) -> str:
        if value == "✓":
            return "color: #3ddc97; font-weight: 700"
        if value == "✗":
            return "color: #ff6b6b"
        return "color: #888"

    st.dataframe(
        pd.DataFrame(rows).style.map(paint_mark, subset=["Đạt"]),
        hide_index=True,
        width="stretch",
        alt="Checklist CANSLIM đầy đủ C, A, N, S, L, I, M",
    )
    st.caption(
        "Theo William J. O'Neil. Ngưỡng chỉnh trong config.CANSLIM. "
        "I (tổ chức) chưa có nguồn dữ liệu nên để N/A; M cần dữ liệu VNINDEX. "
        "L so với các mã có cache giá trong data/ohlcv."
    )


def recommendation_stop(symbol: str) -> float | None:
    matched = PORTFOLIO.loc[PORTFOLIO["Mã CK"].astype(str).str.upper() == symbol, "Giá cắt lỗ động"]
    if matched.empty:
        return None
    value = pd.to_numeric(matched.iloc[0], errors="coerce")
    if pd.isna(value):
        return None
    return float(value)


def position_plan(
    price: float, stop: float, capital: float, risk_pct: float
) -> dict[str, float] | str:
    """Số cổ phiếu theo rủi ro. Giá bằng cắt lỗ thì không chia."""
    if price <= 0 or capital < 0 or risk_pct < 0:
        return "Giá hoặc vốn không hợp lệ."
    if price <= stop:
        return "Giá đã chạm hoặc thủng cắt lỗ. Không tính khối lượng mua."
    gap_vnd = round((price - stop) * THOUSAND_VND)
    if gap_vnd <= 0:
        return "Khoảng cách cắt lỗ không đủ để chia."
    max_loss = capital * (risk_pct / 100)
    shares = math.floor(max_loss / gap_vnd)
    return {
        "distance_pct": (price - stop) / price * 100,
        "max_loss": max_loss,
        "shares": float(shares),
        "gap_vnd": gap_vnd,
    }


def show_position(symbol: str, price: float, bars: pd.DataFrame, capital: float, risk_pct: float) -> None:
    stop = recommendation_stop(symbol)
    source = "bảng khuyến nghị"
    if stop is None:
        window = bars.tail(20)
        stop = float(window["low"].min())
        source = "đáy 20 phiên, vì mã không có trong bảng khuyến nghị"
    plan = position_plan(price, stop, capital, risk_pct)
    st.sidebar.subheader("Khối lượng mua")
    st.sidebar.caption(f"{symbol}: giá {price:.2f}, cắt lỗ {stop:.2f} ({source}).")
    if isinstance(plan, str):
        st.sidebar.warning(plan)
        return
    st.sidebar.write(
        f"Khoảng cách cắt lỗ {plan['distance_pct']:.1f}%. "
        f"Số tiền chấp nhận mất {plan['max_loss']:,.0f} đ."
    )
    probe_cash = capital / 4
    price_vnd = price * THOUSAND_VND
    shares_by_cash = math.floor(probe_cash / price_vnd) if price_vnd > 0 else 0
    shares_by_risk = math.floor(plan["shares"] / 4)
    probe_shares = min(shares_by_cash, shares_by_risk)
    st.sidebar.markdown(f"### Lệnh 1: {probe_shares:,.0f} cổ phiếu")
    st.sidebar.caption(
        "Số cổ phiếu lấy theo khoảng cách tới giá cắt lỗ, và không vượt số tiền 1/4 vốn. "
        f"Nếu mua hết 1/4 vốn được {shares_by_cash:,.0f} cổ phiếu. "
        "Làm tròn xuống. Giá nghìn đồng được nhân 1.000 khi đổi ra đồng. "
        f"Toàn bộ vị thế theo mức rủi ro là {plan['shares']:,.0f} cổ phiếu."
    )


def main() -> None:
    st.set_page_config(page_title="Quét thị trường", layout="wide")
    st.title("Quét thị trường")
    st.caption(
        "Bảng Top 20 đọc từ top20_cache.csv. "
        "Lần quét lấy giá (KBS) và ROE quý mới nhất song song, rồi lọc ROE và thanh khoản."
    )

    with st.sidebar:
        st.header("Phiên và vốn")
        status, clock = market_session()
        st.metric("Trạng thái", status)
        st.caption(f"Giờ Hà Nội {clock}. Sáng 9:00–11:30, chiều 13:00–14:45.")
        capital = st.number_input("Tổng số vốn dự định đầu tư (VND)", value=100_000_000, min_value=0, step=1_000_000)
        risk_pct = st.slider("Mức rủi ro tối đa chấp nhận trên tổng vốn (%)", 1, 5, 2)
        probe = float(capital) / 4
        st.markdown(f"Số tiền cho Lệnh 1 dò đường (1/4 vốn): {probe:,.0f} VND")
        st.caption(f"Lệnh 2, 3 và 4 mỗi lệnh {probe:,.0f} VND. Ba phần sau chờ giá vượt đáy trung tâm.")
        st.header("Dữ liệu")
        refresh = st.button("Quét và làm mới dữ liệu", width="stretch")
        if CACHE_PATH.exists():
            st.caption(f"Cache: data/{CACHE_PATH.name}")
        else:
            st.caption("Chưa có file cache.")

    if refresh:
        board, errors = scan_top20()
        st.session_state["scan_errors"] = errors
        if board.empty:
            st.session_state["scan_note"] = "Quét xong nhưng không có mã qua lọc ROE và thanh khoản."
        else:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            board.to_csv(CACHE_PATH, index=False)
            st.session_state["scan_note"] = f"Đã ghi {len(board)} mã vào {CACHE_PATH.name}."
        st.rerun()

    note = st.session_state.get("scan_note")
    if note:
        st.sidebar.info(note)
    for message in st.session_state.get("scan_errors", []):
        st.sidebar.text(message)

    try:
        board = read_cache()
    except Exception as error:
        st.error(f"Không đọc được cache: {error}")
        return

    options = board["Mã"].astype(str).tolist() if not board.empty else []
    if "POW" not in options:
        options = ["POW", *options]
    selected = st.selectbox("Mã trong Top 20", options, index=options.index("POW"))
    typed = st.text_input(
        "Hoặc gõ mã khác",
        value="",
        placeholder="Để trống để dùng mã trong hộp chọn",
    ).strip().upper()
    symbol = typed or selected

    start = (date.today() - timedelta(days=CHART_DAYS)).isoformat()
    try:
        bars = load_bars(symbol, start)
    except Exception as error:
        st.error(f"Không lấy được đồ thị {symbol}: {error}")
        return
    if bars.empty or bars["close"].dropna().shape[0] < 20:
        st.warning(f"{symbol} chưa đủ phiên để tính MA20.")
        return
    try:
        base = support_scan(bars)
        neckline = float(base["neckline"])
    except Exception as error:
        base = None
        neckline = None
        st.warning(f"Không quét được đáy 6 tháng của {symbol}: {error}")
    show_position(symbol, float(bars["close"].iloc[-1]), bars, float(capital), float(risk_pct))

    station, classroom = st.tabs(["Trạm Đầu Tư Thực Chiến", "Trạm Học Tập & Đọc Vị Nến"])
    with station:
        st.subheader(f"Top {min(TOP_N, len(board))} dẫn dắt" if not board.empty else "Top 20 dẫn dắt")
        if board.empty:
            st.info("Chưa có top20_cache.csv. Bấm «Quét và làm mới dữ liệu» ở thanh bên.")
        else:
            st.dataframe(
                style_board(board),
                hide_index=True,
                width="stretch",
                alt="Top cổ phiếu theo sức mạnh giá 3 tháng sau lọc thanh khoản và ROE",
            )
        show_charts(symbol, bars, neckline)
        commentary(symbol, bars)
        show_money_flow(symbol, bars)
        show_patterns(symbol, bars)
        if base is not None:
            show_support(base)
        show_valuation(symbol)
    with classroom:
        show_candle_lesson(symbol, bars)
        show_canslim(symbol, bars)


if __name__ == "__main__":
    main()
