"""Dashboard theo dõi cổ phiếu Việt Nam bằng vnstock 5 và Streamlit."""

from datetime import date, timedelta

import pandas as pd
import pandas_ta  # đăng ký df.ta
import plotly.graph_objects as go
import streamlit as st
from vnstock import Market

LOOKBACK_DAYS = 365


@st.cache_data(ttl=300, show_spinner=False)
def load_prices(symbol: str) -> pd.DataFrame:
    """Lấy OHLCV ngày bằng vnstock 5 rồi chuẩn hóa cột và chỉ báo."""
    end = date.today()
    start = end - timedelta(days=LOOKBACK_DAYS)
    raw = Market().equity(symbol).ohlcv(
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1D",
    )
    frame = raw.rename(
        columns={
            "time": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.set_index("Date").sort_index()
    frame = frame[["Open", "High", "Low", "Close", "Volume"]]

    # pandas_ta 0.4.x không có df.ta.ma. SMA 20 chính là MA chu kỳ 20.
    frame.ta.rsi(append=True)
    frame.ta.sma(length=20, append=True)
    return frame


def _chart_x(frame: pd.DataFrame) -> list[str]:
    """Ngày dương lịch, không kèm múi giờ. Plotly nhận list số, không nhận mảng nhị phân."""
    index = frame.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_convert("Asia/Ho_Chi_Minh")
    return [ts.strftime("%Y-%m-%d") for ts in index]


def _chart_layout(figure: go.Figure, title: str, height: int, y_title: str) -> None:
    figure.update_layout(
        template="plotly_dark",
        title=title,
        yaxis_title=y_title,
        height=height,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font={"color": "#f0f2f6"},
        margin={"l": 40, "r": 20, "t": 50, "b": 30},
        legend={"orientation": "h", "y": 1.08},
    )


def candle_chart(symbol: str, frame: pd.DataFrame) -> go.Figure:
    dates = _chart_x(frame)
    figure = go.Figure()
    figure.add_trace(
        go.Candlestick(
            x=dates,
            open=frame["Open"].tolist(),
            high=frame["High"].tolist(),
            low=frame["Low"].tolist(),
            close=frame["Close"].tolist(),
            name="Giá",
            increasing={"line": {"color": "#3ddc97"}, "fillcolor": "#3ddc97"},
            decreasing={"line": {"color": "#ff6b6b"}, "fillcolor": "#ff6b6b"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=[None if pd.isna(v) else float(v) for v in frame["SMA_20"]],
            mode="lines",
            name="MA20",
            line={"color": "#f4a261", "width": 1.8},
        )
    )
    _chart_layout(figure, f"{symbol} — nến ngày và MA20", 520, "Giá (nghìn VND)")
    figure.update_layout(xaxis_rangeslider_visible=False)
    return figure


def rsi_chart(frame: pd.DataFrame) -> go.Figure:
    dates = _chart_x(frame)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=[None if pd.isna(v) else float(v) for v in frame["RSI_14"]],
            mode="lines",
            name="RSI 14",
            line={"color": "#4cc9f0", "width": 1.6},
        )
    )
    figure.add_hline(y=70, line_dash="dash", line_color="#ff6b6b")
    figure.add_hline(y=30, line_dash="dash", line_color="#3ddc97")
    _chart_layout(figure, "RSI 14", 260, "RSI")
    figure.update_layout(yaxis={"range": [0, 100], "title": "RSI"}, showlegend=False)
    return figure


def show_signal(rsi: float) -> None:
    if rsi < 30:
        st.success(f"RSI {rsi:.1f}: Vùng quá bán - Cân nhắc MUA")
    elif rsi > 70:
        st.warning(f"RSI {rsi:.1f}: Vùng quá mua - Cân nhắc BÁN")
    else:
        st.info(f"RSI {rsi:.1f}: ngoài vùng quá mua và quá bán.")


def main() -> None:
    st.set_page_config(page_title="Cổ phiếu Việt Nam", layout="wide")
    st.title("Theo dõi cổ phiếu Việt Nam")
    st.caption("Nguồn: vnstock 5 · Market().equity().ohlcv() · RSI 14 và MA20 bằng pandas_ta")

    symbol = st.text_input("Mã cổ phiếu", value="FPT").strip().upper()
    if not symbol:
        st.info("Nhập một mã, ví dụ FPT, HPG hoặc VNM.")
        return

    try:
        with st.spinner(f"Đang lấy dữ liệu {symbol}..."):
            frame = load_prices(symbol)
    except Exception as error:
        st.error(f"Không lấy được dữ liệu {symbol}: {error}")
        return

    if frame.empty or frame["RSI_14"].dropna().empty:
        st.warning("Không đủ phiên để tính RSI.")
        return

    latest = frame.iloc[-1]
    rsi = float(frame["RSI_14"].dropna().iloc[-1])
    columns = st.columns(4)
    columns[0].metric("Đóng cửa", f"{latest['Close']:.2f}")
    columns[1].metric("MA20", f"{latest['SMA_20']:.2f}" if pd.notna(latest["SMA_20"]) else "—")
    columns[2].metric("RSI 14", f"{rsi:.1f}")
    columns[3].metric("Khối lượng", f"{latest['Volume']:,.0f}")
    show_signal(rsi)

    # theme=None giữ màu nến tự khai báo. Theme mặc định của Streamlit đổi nến thành #000032, gần như đen trên nền tối.
    st.plotly_chart(
        candle_chart(symbol, frame),
        theme=None,
        alt=f"Nến ngày và MA20 của {symbol}",
    )
    st.plotly_chart(
        rsi_chart(frame),
        theme=None,
        alt=f"RSI 14 của {symbol}",
    )


if __name__ == "__main__":
    main()
