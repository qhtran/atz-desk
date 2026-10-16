"""Trang Khuyến nghị ngắn hạn, mô phỏng bảng YSradar bằng vnstock 5."""

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from vnstock import Market

# Giá theo nghìn đồng, cùng đơn vị ohlcv của vnstock (24.400 → 24.4).
PORTFOLIO = pd.DataFrame(
    {
        "Mã CK": ["VPB", "PVS", "TCB", "GVR", "HDB"],
        "Ngày khuyến nghị": [
            "2026-09-09",
            "2026-09-07",
            "2026-09-07",
            "2026-08-28",
            "2026-07-15",
        ],
        "Giá mua": [21.733, 32.250, 32.600, 32.950, 20.626],
        "Giá mục tiêu": [26.410, 37.930, 35.110, 37.820, 22.450],
        "Giá cắt lỗ động": [20.600, 30.200, 30.300, 30.100, 20.000],
        "Khuyến nghị": ["Nắm giữ", "Nắm giữ", "Nắm giữ", "Nắm giữ", "Nắm giữ"],
    }
)


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is not None:
        parsed = parsed.tz_convert("Asia/Ho_Chi_Minh")
    return parsed.date()


def _chart_dates(index: pd.Index) -> list[str]:
    stamps = pd.to_datetime(index)
    if getattr(stamps, "tz", None) is not None:
        stamps = stamps.tz_convert("Asia/Ho_Chi_Minh")
    return [stamp.strftime("%Y-%m-%d") for stamp in stamps]


@st.cache_data(ttl=300, show_spinner=False)
def load_recent(symbol: str) -> pd.DataFrame:
    """20 phiên gần nhất: giá hiện tại, MA20 và khối lượng trung bình."""
    frame = Market().equity(symbol).ohlcv(length=20, interval="1D")
    frame = frame.sort_values("time")
    return frame


@st.cache_data(ttl=300, show_spinner=False)
def load_history(symbol: str, start: str) -> pd.DataFrame:
    """Lịch sử từ trước ngày khuyến nghị để đếm phiên và vẽ nến."""
    frame = Market().equity(symbol).ohlcv(
        start=start,
        end=date.today().isoformat(),
        interval="1D",
    )
    return frame.sort_values("time")


def build_board() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[str]]:
    """Ghép danh mục giả lập với giá vnstock. Một mã lỗi không làm dừng cả bảng."""
    rows: list[dict[str, object]] = []
    history: dict[str, pd.DataFrame] = {}
    errors: list[str] = []

    for item in PORTFOLIO.itertuples(index=False):
        symbol = str(item[0])
        recommended = date.fromisoformat(str(item[1]))
        buy = float(item[2])
        target = float(item[3])
        stop = float(item[4])
        status = str(item[5])
        row: dict[str, object] = {
            "Ngày khuyến nghị": recommended.strftime("%d/%m/%Y"),
            "Mã CK": symbol,
            "Khuyến nghị": status,
            "Giá mua": buy,
            "Giá mục tiêu": target,
            "Giá cắt lỗ động": stop,
            "Giá TT": pd.NA,
            "LN tạm tính (%)": pd.NA,
            "KLGD TB 20 phiên": pd.NA,
            "Xu hướng": pd.NA,
            "Nắm giữ T+": pd.NA,
        }
        try:
            recent = load_recent(symbol)
            last_close = float(recent["close"].iloc[-1])
            moving_average = float(recent["close"].tail(20).mean())
            average_volume = float(recent["volume"].tail(20).mean())
            row["Giá TT"] = last_close
            row["LN tạm tính (%)"] = round((last_close - buy) / buy * 100, 2)
            row["KLGD TB 20 phiên"] = average_volume
            row["Xu hướng"] = "Tăng" if last_close > moving_average else "Giảm"
        except Exception as error:
            errors.append(f"{symbol}: không lấy được 20 phiên gần nhất ({error})")

        try:
            start = (recommended - timedelta(days=40)).isoformat()
            bars = load_history(symbol, start)
            history[symbol] = bars
            session_days = [_as_date(value) for value in bars["time"]]
            # T+ trên YSradar đếm phiên sau ngày khuyến nghị, tới phiên gần nhất.
            held = sum(day > recommended for day in session_days)
            row["Nắm giữ T+"] = f"T+{held}"
        except Exception as error:
            errors.append(f"{symbol}: không đếm được số phiên nắm giữ ({error})")
            row["Nắm giữ T+"] = "—"
        rows.append(row)

    return pd.DataFrame(rows), history, errors


def style_board(board: pd.DataFrame):
    def paint_pnl(value: object) -> str:
        if pd.isna(value):
            return ""
        if float(value) > 0:
            return "color: #3ddc97"
        if float(value) < 0:
            return "color: #ff6b6b"
        return ""

    def paint_trend(value: object) -> str:
        if value == "Tăng":
            return "color: #3ddc97; font-weight: 600"
        if value == "Giảm":
            return "color: #ff6b6b; font-weight: 600"
        return ""

    return (
        board.style.format(
            {
                "Giá mua": "{:.3f}",
                "Giá mục tiêu": "{:.3f}",
                "Giá cắt lỗ động": "{:.3f}",
                "Giá TT": "{:.3f}",
                "LN tạm tính (%)": "{:+.2f}",
                "KLGD TB 20 phiên": "{:,.0f}",
            },
            na_rep="—",
        )
        .map(paint_pnl, subset=["LN tạm tính (%)"])
        .map(paint_trend, subset=["Xu hướng"])
    )


def candle_chart(symbol: str, frame: pd.DataFrame, levels: pd.Series) -> go.Figure:
    dates = _chart_dates(frame["time"])
    figure = go.Figure()
    figure.add_trace(
        go.Candlestick(
            x=dates,
            open=frame["open"].tolist(),
            high=frame["high"].tolist(),
            low=frame["low"].tolist(),
            close=frame["close"].tolist(),
            name="Giá",
            increasing={"line": {"color": "#3ddc97"}, "fillcolor": "#3ddc97"},
            decreasing={"line": {"color": "#ff6b6b"}, "fillcolor": "#ff6b6b"},
        )
    )
    ma20 = frame["close"].rolling(20).mean()
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=[None if pd.isna(value) else float(value) for value in ma20],
            mode="lines",
            name="MA20",
            line={"color": "#f4a261", "width": 1.6},
        )
    )
    recommended = datetime.strptime(str(levels["Ngày khuyến nghị"]), "%d/%m/%Y").date()
    figure.add_vline(x=recommended.isoformat(), line_dash="dot", line_color="#f0f2f6")
    for name, color in (
        ("Giá mua", "#4cc9f0"),
        ("Giá mục tiêu", "#3ddc97"),
        ("Giá cắt lỗ động", "#ff6b6b"),
    ):
        figure.add_hline(
            y=float(levels[name]),
            line_dash="dash",
            line_color=color,
            annotation_text=name,
            annotation_position="right",
        )
    figure.update_layout(
        template="plotly_dark",
        title=f"{symbol} — nến ngày, MA20, giá mua / mục tiêu / cắt lỗ",
        yaxis_title="Giá (nghìn đồng)",
        height=520,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font={"color": "#f0f2f6"},
        xaxis_rangeslider_visible=False,
        margin={"l": 40, "r": 20, "t": 50, "b": 30},
        legend={"orientation": "h", "y": 1.08},
    )
    return figure


def watch_notes(board: pd.DataFrame) -> list[str]:
    notes: list[str] = []
    for item in board.itertuples(index=False):
        price = item[6]
        if pd.isna(price):
            continue
        price = float(price)
        target = float(item[4])
        stop = float(item[5])
        symbol = str(item[1])
        if price >= target:
            notes.append(f"{symbol} đã chạm hoặc vượt giá mục tiêu {target:.3f}.")
        elif price > stop:
            gap = (price - stop) / stop * 100
            if gap <= 8:
                notes.append(f"{symbol} còn cách cắt lỗ {stop:.3f} khoảng {gap:.0f}%.")
    return notes


def main() -> None:
    st.set_page_config(page_title="Khuyến nghị ngắn hạn", layout="wide")
    st.title("Khuyến nghị ngắn hạn")
    st.caption("Danh mục mô phỏng YSradar · Giá TT, MA20 và khối lượng lấy từ vnstock 5")

    with st.spinner("Đang lấy giá 5 mã..."):
        board, history, errors = build_board()

    for message in errors:
        st.warning(message)

    pnl = board["LN tạm tính (%)"].dropna()
    average = float(pnl.mean()) if not pnl.empty else float("nan")
    with st.container(border=True):
        st.markdown("**% Lợi nhuận TB**")
        if pd.isna(average):
            st.markdown("Chưa đủ giá để tính.")
        else:
            color = "#3ddc97" if average >= 0 else "#ff6b6b"
            st.markdown(
                f"<p style='font-size:2.6rem;font-weight:700;color:{color};margin:0'>{average:+.2f}%</p>",
                unsafe_allow_html=True,
            )
        st.caption("Trung bình cộng cột LN tạm tính (%) của các mã lấy được giá.")

    st.dataframe(
        style_board(board),
        hide_index=True,
        width="stretch",
        alt="Danh mục khuyến nghị ngắn hạn: giá mua, mục tiêu, cắt lỗ, lãi tạm tính và xu hướng",
    )
    for note in watch_notes(board):
        st.caption(note)

    symbols = board["Mã CK"].tolist()
    selected = st.selectbox("Xem đồ thị", symbols)
    chosen = board.loc[board["Mã CK"] == selected].iloc[0]
    bars = history.get(selected)
    if bars is None or bars.empty:
        st.info(f"Chưa có chuỗi giá để vẽ {selected}.")
        return
    st.plotly_chart(
        candle_chart(selected, bars, chosen),
        theme=None,
        alt=f"Nến ngày của {selected} với giá mua, giá mục tiêu và cắt lỗ",
    )


if __name__ == "__main__":
    main()
