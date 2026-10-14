"""Các hàm dựng đồ thị Plotly. Mỗi hàm nhận khung đã qua indicators.enrich() và trả một Figure riêng.
Chiều cao, màu sắc nằm trong config.CHART."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

import config

S = config.CHART


def _dates(w: pd.DataFrame) -> list[str]:
    return [day.strftime("%Y-%m-%d") for day in w["_day"]]


def _vals(series: pd.Series) -> list[float | None]:
    return [None if pd.isna(v) else float(v) for v in series]


def _line(fig, x, series, name, color, width=1.4, dash=None):
    style = {"color": color, "width": width}
    if dash:
        style["dash"] = dash
    fig.add_trace(go.Scatter(x=x, y=_vals(series), mode="lines", name=name, line=style))


def _layout(fig, title, height, legend_right=True):
    fig.update_layout(
        template="plotly_dark", title=title, height=height,
        paper_bgcolor=S["BG"], plot_bgcolor=S["BG"], font={"color": S["FONT"]},
        xaxis_rangeslider_visible=False,
        margin={"l": 40, "r": 140 if legend_right else 20, "t": 60, "b": 30},
        legend={"orientation": "v", "yanchor": "top", "y": 1, "xanchor": "left", "x": 1.02},
    )
    fig.update_xaxes(type="category", nticks=12)
    return fig


def candle_chart(symbol: str, w: pd.DataFrame, neckline: float | None = None) -> go.Figure:
    """Nến + MA20/MA50 + Bollinger + đáy trung tâm."""
    x = _dates(w)
    fig = go.Figure(go.Candlestick(
        x=x, open=w["open"].tolist(), high=w["high"].tolist(), low=w["low"].tolist(),
        close=w["close"].tolist(), name="Giá",
        increasing={"line": {"color": S["UP"]}, "fillcolor": S["UP"]},
        decreasing={"line": {"color": S["DOWN"]}, "fillcolor": S["DOWN"]},
    ))
    _line(fig, x, w["MA20"], "MA20", S["MA20"], 1.8)
    _line(fig, x, w["MA50"], "MA50", S["MA50"], 1.8)
    _line(fig, x, w["BB_U"], "BB trên", S["BB"], 1.2)
    _line(fig, x, w["BB_M"], "BB giữa", S["BB_MID"], 1.2, "dot")
    _line(fig, x, w["BB_L"], "BB dưới", S["BB"], 1.2)
    if neckline is not None and neckline > 0:
        fig.add_hline(y=neckline, line_dash="dash", line_color=S["NECKLINE"],
                      annotation_text="Đáy trung tâm", annotation_font_color=S["NECKLINE"])
    _layout(fig, f"{symbol} — nến ngày, MA20/MA50, Bollinger ({config.BB_LENGTH}, {config.BB_STD:g})",
            S["MAIN_HEIGHT"])
    fig.update_yaxes(title_text="Giá (nghìn đồng)")
    return fig


def volume_chart(symbol: str, w: pd.DataFrame) -> go.Figure:
    x = _dates(w)
    colors = [S["UP"] if c >= o else S["DOWN"] for c, o in zip(w["close"], w["open"])]
    fig = go.Figure(go.Bar(x=x, y=w["volume"].tolist(), name="Khối lượng", marker_color=colors))
    _line(fig, x, w["VOL_AVG"], f"KL TB{config.VOLUME_AVG}", S["VOL_AVG"])
    return _layout(fig, f"{symbol} — khối lượng và TB{config.VOLUME_AVG}", S["SUB_HEIGHT"])


def rsi_chart(symbol: str, w: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    _line(fig, _dates(w), w["RSI"], "RSI", S["RSI"])
    for level in (config.RSI_OVERBOUGHT, config.RSI_OVERSOLD):
        fig.add_hline(y=level, line_dash="dot", line_color=S["REF"])
    fig.update_yaxes(range=[0, 100])
    return _layout(fig, f"{symbol} — RSI({config.RSI_LENGTH})", S["SUB_HEIGHT"])


def macd_chart(symbol: str, w: pd.DataFrame) -> go.Figure:
    x = _dates(w)
    colors = [S["UP"] if v >= 0 else S["DOWN"] for v in w["MACD_HIST"].fillna(0)]
    fig = go.Figure(go.Bar(x=x, y=_vals(w["MACD_HIST"]), name="Histogram", marker_color=colors))
    _line(fig, x, w["MACD"], "MACD", S["MACD"])
    _line(fig, x, w["MACD_SIG"], "Signal", S["MACD_SIGNAL"])
    return _layout(fig, f"{symbol} — MACD({config.MACD_FAST},{config.MACD_SLOW},{config.MACD_SIGNAL})",
                   S["SUB_HEIGHT"])


def mfi_chart(symbol: str, w: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    _line(fig, _dates(w), w["MFI"], "MFI", S["MFI"])
    for level in (80, 20):
        fig.add_hline(y=level, line_dash="dot", line_color=S["REF"])
    fig.update_yaxes(range=[0, 100])
    return _layout(fig, f"{symbol} — MFI({config.MFI_LENGTH}), dòng tiền", S["SUB_HEIGHT"])


# Tên tab con -> hàm dựng. Thêm/bớt chỉ báo chỉ cần sửa ở đây.
INDICATOR_CHARTS = {
    "Khối lượng": volume_chart,
    "RSI": rsi_chart,
    "MACD": macd_chart,
    "MFI": mfi_chart,
}
