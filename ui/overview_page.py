"""Tab Tổng quan: chỉ số Việt Nam và quốc tế.

Thiếu file local thì hỏi vnstock. Chỉ số quốc tế lấy từ Yahoo Finance.
Cột không có trong nguồn giữ «—». Lỗi mạng không làm vỡ trang.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd
import streamlit as st

from ui.mobile import pinned

from config import BARS_DIR

VN_INDEXES = ("VNIndex", "HNXIndex", "UPIndex", "VN30", "VN30F1M", "VN30F2M")
# Tên hiển thị -> mã vnstock. Thử KBS trước, VCI sau. HĐTL VN30 thường chỉ có trên VCI.
_VN_SYMBOLS = {
    "VNIndex": "VNINDEX",
    "HNXIndex": "HNXINDEX",
    "UPIndex": "UPCOMINDEX",
    "VN30": "VN30",
    "VN30F1M": "VN30F1M",
    "VN30F2M": "VN30F2M",
}
_VN_SOURCES = ("kbs", "vci")
VN_COLUMNS = (
    "Chỉ số",
    "Tham chiếu",
    "Đóng cửa",
    "Tăng/giảm (điểm/%)",
    "Mũi tên",
    "Tổng KL khớp (triệu CP)",
    "KL thỏa thuận (triệu CP)",
    "Tổng GT khớp (tỷ)",
    "GT thỏa thuận (tỷ)",
    "GT dòng NN",
    "GT tự doanh",
    "KL TB 10 phiên",
    "GT TB 10 phiên",
)
# Nhãn hiển thị và mã Yahoo Finance. Không ghi số liệu vào đây.
WORLD = (
    ("Mỹ", (
        ("DJ", "^DJI"),
        ("NASDAQ", "^IXIC"),
        ("S&P500", "^GSPC"),
        ("Hợp đồng tương lai DJ", "YM=F"),
    )),
    ("Châu Âu", (
        ("FTSE100", "^FTSE"),
        ("DAX", "^GDAXI"),
        ("CAC 40", "^FCHI"),
    )),
    ("Châu Á", (
        ("Nikkei 225", "^N225"),
        ("Shanghai Composite", "000001.SS"),
        ("Hang Seng", "^HSI"),
        ("KOSPI", "^KS11"),
    )),
)
WORLD_COLUMNS = ("Khu vực", "Chỉ số", "Đóng cửa", "Tăng/giảm (điểm/%)", "Mũi tên")
_SHARES = 1_000_000
_BILLION = 1_000_000_000
_VALUE_COLUMNS = ("value", "total_value", "match_value", "turnover")
_MATCH_VALUE = ("total_match_value", "matched_value", "match_value")
_DEAL_VOLUME = ("total_deal_volume", "deal_volume")
_DEAL_VALUE = ("total_deal_value", "deal_value")
_FLOW_NET = ("net_val",)
_FLOW_BUY = ("buy_val",)
_FLOW_SELL = ("sell_val",)
_CACHE_TTL = 10 * 60
_PAINTED = ("Tăng/giảm (điểm/%)", "Mũi tên", "GT dòng NN", "GT tự doanh")


def _blank(columns: tuple[str, ...]) -> dict[str, str]:
    return {name: "—" for name in columns}


def _arrow(change: float | None) -> str:
    if change is None:
        return "—"
    if change > 0:
        return "▲"
    if change < 0:
        return "▼"
    return "●"


def _bars_from_frame(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """Chuẩn hóa nến: một dòng mỗi ngày, đóng cửa là số."""
    if frame is None or frame.empty or "close" not in frame.columns:
        return None
    work = frame.copy()
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    if "volume" in work.columns:
        work["volume"] = pd.to_numeric(work["volume"], errors="coerce")
    for column in _VALUE_COLUMNS:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
    if "time" in work.columns:
        stamps = pd.to_datetime(work["time"], errors="coerce", utc=True)
        work["_day"] = stamps.dt.date
        work = work.dropna(subset=["_day"]).drop_duplicates("_day", keep="last")
    work = work.dropna(subset=["close"])
    if len(work) < 2:
        return None
    return work


def _load_local(api_symbol: str) -> pd.DataFrame | None:
    path = BARS_DIR / f"{api_symbol}.csv"
    if not path.exists():
        return None
    try:
        return _bars_from_frame(pd.read_csv(path))
    except Exception:
        return None


def _fetch_vn_bars(api_symbol: str) -> pd.DataFrame | None:
    """Nến ngày từ vnstock. KBS trước, hết dữ liệu thì VCI. Lỗi thì None."""
    from datasource.client import call
    from vnstock import Market

    start = (date.today() - timedelta(days=40)).isoformat()
    end = date.today().isoformat()
    for source in _VN_SOURCES:
        try:
            frame = call(
                lambda source=source: Market().index(api_symbol).ohlcv(
                    start=start,
                    end=end,
                    interval="1D",
                    source=source,
                )
            )
        except Exception:
            continue
        parsed = _bars_from_frame(frame)
        if parsed is not None:
            return parsed
    return None


def _series_value(frame: pd.DataFrame, names: tuple[str, ...]) -> pd.Series | None:
    for name in names:
        if name in frame.columns and frame[name].notna().any():
            return frame[name]
    return None


def _format_million(value: float) -> str:
    return f"{value / _SHARES:,.2f}"


def _format_billion(value: float, signed: bool = False) -> str:
    amount = value / _BILLION
    if signed:
        return f"{amount:+,.2f}"
    return f"{amount:,.2f}"


def _sort_sessions(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """Sắp phiên tăng dần. trade_history dùng trading_date, flow dùng time."""
    if frame is None or frame.empty:
        return None
    work = frame.copy()
    for column in ("trading_date", "time", "date"):
        if column not in work.columns:
            continue
        work["_day"] = pd.to_datetime(work[column], errors="coerce", utc=True)
        work = work.dropna(subset=["_day"]).sort_values("_day")
        work = work.drop_duplicates("_day", keep="last")
        return work if not work.empty else None
    return work


def _window() -> tuple[str, str]:
    start = (date.today() - timedelta(days=40)).isoformat()
    return start, date.today().isoformat()


def _fetch_trade_history(api_symbol: str) -> pd.DataFrame | None:
    """Thống kê khớp và thỏa thuận. trade_history trước, trading_stats sau. VCI rồi KBS."""
    from datasource.client import call
    from vnstock import Market

    start, end = _window()
    market = Market().index(api_symbol)
    for source in ("vci", "kbs"):
        for loader in (
            lambda source=source: market.trade_history(start=start, end=end, source=source),
            lambda source=source: market.trading_stats(start=start, end=end, source=source),
        ):
            try:
                frame = call(loader)
            except Exception:
                continue
            parsed = _sort_sessions(frame)
            if parsed is not None and _series_value(parsed, _MATCH_VALUE + _DEAL_VOLUME + _DEAL_VALUE) is not None:
                return parsed
    return None


def _fetch_flow(api_symbol: str, kind: str) -> pd.DataFrame | None:
    """Dòng tiền. Ưu tiên hàm trên index nếu có, rồi equity, nguồn vci."""
    from datasource.client import call
    from vnstock import Market

    start, end = _window()
    targets = []
    index_fn = getattr(Market().index(api_symbol), kind, None)
    if callable(index_fn):
        targets.append(index_fn)
    equity_fn = getattr(Market().equity(api_symbol), kind, None)
    if callable(equity_fn):
        targets.append(equity_fn)
    for fn in targets:
        try:
            frame = call(lambda fn=fn: fn(start=start, end=end, limit=30, source="vci"))
        except Exception:
            continue
        parsed = _sort_sessions(frame)
        if parsed is not None:
            return parsed
    return None


def _latest_number(frame: pd.DataFrame, names: tuple[str, ...]) -> float | None:
    series = _series_value(frame, names)
    if series is None or pd.isna(series.iloc[-1]):
        return None
    return float(series.iloc[-1])


def _flow_value(frame: pd.DataFrame | None) -> float | None:
    if frame is None:
        return None
    net = _latest_number(frame, _FLOW_NET)
    if net is not None:
        return net
    buy = _latest_number(frame, _FLOW_BUY)
    sell = _latest_number(frame, _FLOW_SELL)
    if buy is None or sell is None:
        return None
    return buy - sell


def _apply_gold(row: dict[str, str], api_symbol: str) -> None:
    """Điền cột còn trống từ bản Gold. Thiếu trường nào thì giữ «—»."""
    try:
        history = _fetch_trade_history(api_symbol)
    except Exception:
        history = None
    if history is not None:
        matched = _series_value(history, _MATCH_VALUE)
        if matched is not None and pd.notna(matched.iloc[-1]):
            row["Tổng GT khớp (tỷ)"] = _format_billion(float(matched.iloc[-1]))
            window = matched.dropna().tail(10)
            if len(window) >= 10:
                row["GT TB 10 phiên"] = _format_billion(float(window.mean()))
        deal_volume = _latest_number(history, _DEAL_VOLUME)
        if deal_volume is not None:
            row["KL thỏa thuận (triệu CP)"] = _format_million(deal_volume)
        deal_value = _latest_number(history, _DEAL_VALUE)
        if deal_value is not None:
            row["GT thỏa thuận (tỷ)"] = _format_billion(deal_value)
    try:
        foreign = _flow_value(_fetch_flow(api_symbol, "foreign_flow"))
    except Exception:
        foreign = None
    if foreign is not None:
        row["GT dòng NN"] = _format_billion(foreign, signed=True)
    try:
        proprietary = _flow_value(_fetch_flow(api_symbol, "proprietary_flow"))
    except Exception:
        proprietary = None
    if proprietary is not None:
        row["GT tự doanh"] = _format_billion(proprietary, signed=True)


def _apply_volume(row: dict[str, str], frame: pd.DataFrame) -> None:
    volume = _series_value(frame, ("volume",))
    if volume is not None and pd.notna(volume.iloc[-1]):
        row["Tổng KL khớp (triệu CP)"] = _format_million(float(volume.iloc[-1]))
        window = volume.dropna().tail(10)
        if len(window) >= 10:
            row["KL TB 10 phiên"] = _format_million(float(window.mean()))
    traded = _series_value(frame, _VALUE_COLUMNS)
    if traded is None or pd.isna(traded.iloc[-1]):
        return
    row["Tổng GT khớp (tỷ)"] = f"{float(traded.iloc[-1]):,.2f}"
    window = traded.dropna().tail(10)
    if len(window) >= 10:
        row["GT TB 10 phiên"] = f"{float(window.mean()):,.2f}"


def _row_from_bars(name: str, frame: pd.DataFrame | None) -> dict[str, str]:
    row = _blank(VN_COLUMNS)
    row["Chỉ số"] = name
    if frame is None:
        return row
    last = float(frame["close"].iloc[-1])
    reference = float(frame["close"].iloc[-2])
    if reference == 0:
        return row
    points = last - reference
    percent = points / reference * 100
    row["Tham chiếu"] = f"{reference:,.2f}"
    row["Đóng cửa"] = f"{last:,.2f}"
    row["Tăng/giảm (điểm/%)"] = f"{points:+,.2f} / {percent:+.2f}%"
    row["Mũi tên"] = _arrow(points)
    _apply_volume(row, frame)
    return row


def _vietnam_rows() -> list[dict[str, str]]:
    rows = []
    for name in VN_INDEXES:
        api_symbol = _VN_SYMBOLS[name]
        frame = _load_local(api_symbol)
        if frame is None:
            try:
                frame = _fetch_vn_bars(api_symbol)
            except Exception:
                frame = None
        row = _row_from_bars(name, frame)
        try:
            _apply_gold(row, api_symbol)
        except Exception:
            pass
        rows.append(row)
    return rows


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def vietnam_board() -> pd.DataFrame:
    try:
        rows = _vietnam_rows()
    except Exception:
        rows = []
        for name in VN_INDEXES:
            row = _blank(VN_COLUMNS)
            row["Chỉ số"] = name
            rows.append(row)
    return pd.DataFrame(rows, columns=list(VN_COLUMNS))


def _ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _yahoo_closes(ticker: str) -> tuple[float, float] | None:
    """Hai phiên gần nhất. Không lấy được thì None."""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(ticker)}?interval=1d&range=10d"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=8, context=_ssl_context()) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    values = [float(item) for item in closes if item is not None]
    if len(values) < 2:
        return None
    return values[-1], values[-2]


def _world_quote(region: str, label: str, ticker: str) -> dict[str, str]:
    row = _blank(WORLD_COLUMNS)
    row["Khu vực"] = region
    row["Chỉ số"] = label
    try:
        found = _yahoo_closes(ticker)
    except Exception:
        found = None
    if found is None:
        return row
    last, reference = found
    if reference == 0:
        return row
    points = last - reference
    percent = points / reference * 100
    row["Đóng cửa"] = f"{last:,.2f}"
    row["Tăng/giảm (điểm/%)"] = f"{points:+,.2f} / {percent:+.2f}%"
    row["Mũi tên"] = _arrow(points)
    return row


def _world_rows() -> list[dict[str, str]]:
    jobs = [
        (region, label, ticker)
        for region, items in WORLD
        for label, ticker in items
    ]
    found: dict[tuple[str, str], dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_world_quote, region, label, ticker): (region, label)
            for region, label, ticker in jobs
        }
        for future, key in futures.items():
            try:
                found[key] = future.result()
            except Exception:
                row = _blank(WORLD_COLUMNS)
                row["Khu vực"] = key[0]
                row["Chỉ số"] = key[1]
                found[key] = row
    return [found[(region, label)] for region, label, _ticker in jobs]


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def world_board() -> pd.DataFrame:
    try:
        rows = _world_rows()
    except Exception:
        rows = []
        for region, items in WORLD:
            for label, _ticker in items:
                row = _blank(WORLD_COLUMNS)
                row["Khu vực"] = region
                row["Chỉ số"] = label
                rows.append(row)
    return pd.DataFrame(rows, columns=list(WORLD_COLUMNS))


def _paint(value: object) -> str:
    text = str(value)
    if text.startswith("+") or text == "▲":
        return "color: #3ddc97"
    if text.startswith("-") or text == "▼":
        return "color: #ff6b6b"
    return ""


def show_overview() -> None:
    st.caption(
        "VN-Index là sông chính, nhóm ngành là sông nhỏ, cổ phiếu là dòng nước. "
        "Thị trường tăng hay giảm lan theo dòng tiền."
    )
    st.subheader("Chỉ số Việt Nam")
    with st.spinner("Đang lấy chỉ số..."):
        try:
            vietnam = vietnam_board()
        except Exception:
            vietnam = pd.DataFrame(
                [{**_blank(VN_COLUMNS), "Chỉ số": name} for name in VN_INDEXES],
                columns=list(VN_COLUMNS),
            )
        try:
            world = world_board()
        except Exception:
            world = pd.DataFrame(
                [
                    {**_blank(WORLD_COLUMNS), "Khu vực": region, "Chỉ số": label}
                    for region, items in WORLD
                    for label, _ticker in items
                ],
                columns=list(WORLD_COLUMNS),
            )
    st.dataframe(
        vietnam.style.map(_paint, subset=list(_PAINTED)),
        hide_index=True,
        width="stretch",
        column_config=pinned("Chỉ số"),
        alt="Chỉ số Việt Nam: tham chiếu, đóng cửa, biến động, khối lượng và giá trị",
    )
    st.caption(
        "Giá và khối lượng khớp lấy từ nến đã lưu hoặc vnstock. "
        "Giá trị khớp và thỏa thuận lấy từ trade_history (VCI, không có thì KBS). "
        "Dòng nước ngoài và tự doanh lấy từ foreign_flow và proprietary_flow, nguồn VCI, đơn vị tỷ đồng. "
        "Cột không có số giữ «—»."
    )
    st.subheader("Chỉ số quốc tế")
    st.dataframe(
        world.style.map(_paint, subset=["Tăng/giảm (điểm/%)", "Mũi tên"]),
        hide_index=True,
        width="stretch",
        column_config=pinned("Chỉ số"),
        alt="Chỉ số Mỹ, châu Âu và châu Á với mũi tên tăng giảm",
    )
    st.caption("Chỉ số quốc tế lấy từ Yahoo Finance. Không lấy được thì để «—».")
