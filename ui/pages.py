"""Các màn Streamlit. Phần tính toán nằm ở analysis/ và datasource/."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from vnstock import Fundamental

from analysis import candles, patterns
from analysis.canslim import check_a, check_c, check_i, check_l, check_m, check_n, check_s, return_3m, score, universe_returns
from analysis.position import position_plan, recommendation_stop
from analysis.session import market_session
from analysis.screening import apply_filter
from analysis.support import support_scan
from analysis.technical import enrich, money_flow_summary
from analysis.valuation import valuation_board
from config import (
    CACHE_PATH, CAPITAL_STEP, CAPITAL_TRANCHES, CHART_DAYS, DEFAULT_CAPITAL, MFI_COLD, MFI_HOT,
    MFI_LENGTH, MIN_AVG_VOLUME, MIN_BARS, MIN_ROE, RISK_DEFAULT, RISK_MAX, RISK_MIN, RS_FILTER_OFF,
    RSI_LENGTH, RSI_OVERBOUGHT, RSI_OVERSOLD, THOUSAND_VND, TOP_N, UNIVERSE, VOLUME_SPIKE,
)
from datasource.cache import read_cache, read_universe
from datasource.client import call, load_bars, load_index_bars
from datasource.fundamentals import eps_growth, latest_roe, ratio_quarterly, stored_roe
import config
import ui.charts as charts


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


def render_sidebar() -> tuple[float, float]:
    with st.sidebar:
        st.header("Phiên và vốn")
        status, clock = market_session()
        st.metric("Trạng thái", status)
        st.caption(f"Giờ Hà Nội {clock}. Sáng 9:00–11:30, chiều 13:00–14:45.")
        capital = st.number_input(
            "Tổng số vốn dự định đầu tư (VND)",
            value=DEFAULT_CAPITAL,
            min_value=0,
            step=CAPITAL_STEP,
        )
        risk_pct = st.slider(
            "Mức rủi ro tối đa chấp nhận trên tổng vốn (%)",
            RISK_MIN,
            RISK_MAX,
            RISK_DEFAULT,
        )
        probe = float(capital) / CAPITAL_TRANCHES
        st.markdown(f"Số tiền cho Lệnh 1 dò đường (1/{CAPITAL_TRANCHES} vốn): {probe:,.0f} VND")
        st.caption(
            f"Lệnh 2, 3 và 4 mỗi lệnh {probe:,.0f} VND. Ba phần sau chờ giá vượt đáy trung tâm."
        )
        st.header("Bộ lọc")
        min_roe_pct = st.number_input(
            "ROE tối thiểu (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(MIN_ROE * 100),
            step=0.5,
        )
        min_volume = st.number_input(
            "KLGD trung bình 20 phiên tối thiểu",
            min_value=0.0,
            value=float(MIN_AVG_VOLUME),
            step=10_000.0,
        )
        min_rs = st.number_input(
            "RS 3 tháng tối thiểu (%)",
            min_value=RS_FILTER_OFF,
            max_value=200.0,
            value=RS_FILTER_OFF,
            step=1.0,
            help="Mức sàn không cắt thêm. Tăng số này để chỉ giữ mã mạnh hơn.",
        )
        top_n = st.slider("Số mã hiển thị", min_value=5, max_value=len(UNIVERSE), value=TOP_N)
        st.caption("Mặc định vẫn là Top 20: ROE 12% và khối lượng 100.000. Quét ghi lại đúng bộ mặc định.")
        st.header("Dữ liệu")
        refresh = st.button("Quét và làm mới dữ liệu", width="stretch")
        st.link_button("Tài khoản", "https://auth.atz.vn/if/user/", width="stretch")
        if CACHE_PATH.exists():
            st.caption(f"Đã lưu: data/{CACHE_PATH.name}")
        else:
            st.caption("Chưa có file cache.")
    if refresh:
        from analysis.screening import scan_top20

        progress = st.progress(0, text="Đang quét...")
        board, errors = scan_top20(
            lambda done, total: progress.progress(done / total, text=f"Đã xong {done}/{total}")
        )
        progress.empty()
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
    filters = {
        "min_roe_pct": float(min_roe_pct),
        "min_volume": float(min_volume),
        "min_rs": float(min_rs),
        "top_n": int(top_n),
    }
    return float(capital), float(risk_pct), filters


def show_dashboard(board: pd.DataFrame, note: str | None = None) -> None:
    status, clock = market_session()
    columns = st.columns(2)
    columns[0].metric("Trạng thái thị trường", status)
    columns[1].metric("Giờ Hà Nội", clock)
    st.caption("Sáng 9:00–11:30, chiều 13:00–14:45. Cuối tuần là ngoài phiên.")
    if note:
        st.caption(note)
        st.subheader(f"Kết quả lọc ({len(board)} mã)" if not board.empty else "Kết quả lọc")
    else:
        st.subheader(f"Top {min(TOP_N, len(board))} dẫn dắt" if not board.empty else "Top 20 dẫn dắt")
    if board.empty:
        st.info("Chưa có top20_cache.csv. Quét từ app.py bằng nút «Quét và làm mới dữ liệu».")
        return
    st.dataframe(
        style_board(board),
        hide_index=True,
        width="stretch",
        alt="Top cổ phiếu theo sức mạnh giá 3 tháng sau lọc thanh khoản và ROE",
    )


def show_charts(symbol: str, bars: pd.DataFrame, neckline: float | None) -> None:
    """Nến chính luôn hiện. RSI, MACD, khối lượng và MFI nằm trong expander."""
    work = enrich(bars)
    st.plotly_chart(
        charts.candle_chart(symbol, work, neckline),
        width="stretch",
        theme=None,
        alt=f"Nến ngày, MA20/MA50, Bollinger và đáy trung tâm của {symbol}",
    )
    with st.expander("Chỉ báo: khối lượng, RSI, MACD, MFI", expanded=False):
        for tab, (name, builder) in zip(st.tabs(list(charts.INDICATOR_CHARTS)), charts.INDICATOR_CHARTS.items()):
            with tab:
                st.plotly_chart(builder(symbol, work), width="stretch", theme=None, alt=f"{name} của {symbol}")
        show_money_flow(symbol, work)


def show_money_flow(symbol: str, work: pd.DataFrame) -> None:
    st.subheader("Dòng tiền & chỉ báo")
    summary = money_flow_summary(work)
    cols = st.columns(5)
    cols[0].metric(f"RSI({RSI_LENGTH})", f"{summary['rsi']:.1f}")
    cols[1].metric(f"MFI({MFI_LENGTH})", f"{summary['mfi']:.1f}")
    cols[2].metric("MACD hist", f"{summary['macd_hist']:+.2f}")
    cols[3].metric("KL / TB20", f"{summary['vol_ratio']:.2f}×")
    cols[4].metric("OBV 20 phiên", "Tăng" if summary["obv_up"] else "Giảm")
    notes = []
    if summary["rsi"] >= RSI_OVERBOUGHT:
        notes.append("RSI vùng quá mua")
    elif summary["rsi"] <= RSI_OVERSOLD:
        notes.append("RSI vùng quá bán")
    if summary["macd"] > summary["macd_signal"]:
        notes.append("MACD trên signal (động lượng tăng)")
    else:
        notes.append("MACD dưới signal (động lượng yếu)")
    if summary["mfi"] >= MFI_HOT:
        notes.append(f"MFI > {MFI_HOT}: tiền vào nóng")
    elif summary["mfi"] <= MFI_COLD:
        notes.append(f"MFI < {MFI_COLD}: tiền rút mạnh")
    notes.append("OBV đi lên: dòng tiền tích luỹ" if summary["obv_up"] else "OBV đi xuống: dòng tiền phân phối")
    if summary["vol_ratio"] >= VOLUME_SPIKE:
        notes.append("khối lượng đột biến")
    st.caption(f"{symbol}: " + "; ".join(notes) + ".")


def show_patterns(symbol: str, bars: pd.DataFrame) -> None:
    st.subheader("Mẫu hình kỹ thuật")
    rows = [
        {"Mẫu hình": item["name"], "Khớp": "✓" if item["found"] else "—", "Chi tiết": item["detail"]}
        for item in patterns.detect_all(bars)
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        alt=f"Mẫu hình giá nhận diện tự động cho {symbol}",
    )
    st.caption(
        "Nhận diện bằng quy tắc đơn giản trên nến ngày (ngưỡng trong config.PATTERNS). "
        "Chỉ là gợi ý, luôn kiểm tra lại bằng mắt trên đồ thị."
    )


def commentary(symbol: str, frame: pd.DataFrame) -> None:
    work = enrich(frame)
    price = float(work["close"].iloc[-1])
    ma20 = float(work["MA20"].iloc[-1])
    window = work.tail(config.VOLUME_AVG)
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
        f"Hỗ trợ {config.VOLUME_AVG} phiên {support:.2f}, giá đang cách {above_support:.1f}%. "
        f"Kháng cự {config.VOLUME_AVG} phiên {resistance:.2f}, giá đang cách {below_resistance:.1f}%."
    )


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


def show_candle_lesson(symbol: str, bars: pd.DataFrame) -> None:
    st.subheader("Đọc vị nến phiên gần nhất")
    try:
        name = candles.candle_pattern(bars)
    except Exception as error:
        st.warning(f"Không đọc được nến của {symbol}: {error}")
        return
    if name is None:
        st.info(f"{symbol} chưa khớp Doji, Hammer, Shooting Star hay Engulfing ở phiên cuối.")
        return
    st.info(f"{symbol}: {name}. {candles.explain_pattern(name)}")


def show_canslim(symbol: str, bars: pd.DataFrame) -> None:
    st.subheader("CANSLIM — checklist 7 chữ")
    growth = None
    period = "—"
    roe = None
    try:
        found = eps_growth(symbol)
        if found is not None:
            period, growth = found
    except Exception:
        growth = None
    try:
        roe = stored_roe(symbol)
        if roe is None:
            ratios = call(lambda: ratio_quarterly(Fundamental(), symbol))
            roe = latest_roe(ratios)
    except Exception:
        roe = None
    index_bars = load_index_bars()
    index_ret = return_3m(index_bars) if index_bars is not None else None
    peers = universe_returns()
    rows = [
        check_c(None if growth is None else growth * 100, period),
        check_a(None if roe is None else roe * 100),
        check_n(bars),
        check_s(bars),
        check_l(return_3m(bars), peers, index_ret),
        check_i(),
        check_m(index_bars),
    ]
    passed, rated = score(rows)
    st.metric("Điểm CANSLIM", f"{passed}/{rated}", help="Chỉ tính các chữ có dữ liệu (bỏ N/A).")
    for row in rows:
        mark = row["Đạt"]
        st.markdown(f"**{row['Chữ']} · {mark}** — {row['Tiêu chí']}")
        detail = str(row["Thực tế"])
        note = str(row["Ghi chú"]).strip()
        st.caption(detail if not note else f"{detail}. {note}")
    st.caption(
        "Theo William J. O'Neil. Ngưỡng chỉnh trong config.CANSLIM. "
        "I (tổ chức) chưa có nguồn dữ liệu nên để N/A; M cần dữ liệu VNINDEX. "
        "L so với các mã có cache giá trong data/ohlcv."
    )


def show_position(symbol: str, price: float, bars: pd.DataFrame, capital: float, risk_pct: float) -> None:
    stop = recommendation_stop(symbol)
    source = "bảng khuyến nghị"
    if stop is None:
        window = bars.tail(config.VOLUME_AVG)
        stop = float(window["low"].min())
        source = f"đáy {config.VOLUME_AVG} phiên, vì mã không có trong bảng khuyến nghị"
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
    probe_cash = capital / CAPITAL_TRANCHES
    price_vnd = price * THOUSAND_VND
    shares_by_cash = math.floor(probe_cash / price_vnd) if price_vnd > 0 else 0
    shares_by_risk = math.floor(plan["shares"] / CAPITAL_TRANCHES)
    probe_shares = min(shares_by_cash, shares_by_risk)
    st.sidebar.markdown(f"### Lệnh 1: {probe_shares:,.0f} cổ phiếu")
    st.sidebar.caption(
        "Số cổ phiếu lấy theo khoảng cách tới giá cắt lỗ, và không vượt số tiền 1/4 vốn. "
        f"Nếu mua hết 1/{CAPITAL_TRANCHES} vốn được {shares_by_cash:,.0f} cổ phiếu. "
        "Làm tròn xuống. Giá nghìn đồng được nhân 1.000 khi đổi ra đồng. "
        f"Toàn bộ vị thế theo mức rủi ro là {plan['shares']:,.0f} cổ phiếu."
    )


def prepare(board: pd.DataFrame):
    """Chọn mã và nạp nến. Trả None khi không vẽ được trang mã."""
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
        return None
    if bars.empty or bars["close"].dropna().shape[0] < MIN_BARS:
        st.warning(f"{symbol} chưa đủ phiên để tính MA20.")
        return None
    try:
        base = support_scan(bars)
        neckline = float(base["neckline"])
    except Exception as error:
        base = None
        neckline = None
        st.warning(f"Không quét được đáy 6 tháng của {symbol}: {error}")
    return symbol, bars, base, neckline


def show_symbol_header(symbol: str, bars: pd.DataFrame, board: pd.DataFrame) -> None:
    work = enrich(bars)
    price = float(work["close"].iloc[-1])
    ma20 = float(work["MA20"].iloc[-1]) if pd.notna(work["MA20"].iloc[-1]) else None
    matched = board.loc[board["Mã"].astype(str) == symbol] if not board.empty else board
    columns = st.columns(4)
    columns[0].metric("Giá", f"{price:.2f}")
    columns[1].metric("MA20", f"{ma20:.2f}" if ma20 is not None else "—")
    if matched.empty:
        columns[2].metric("RS 3 tháng", "—")
        columns[3].metric("ROE", "—")
        return
    row = matched.iloc[0]
    columns[2].metric("RS 3 tháng", f"{float(row['RS 3 tháng (%)']):+.1f}%")
    columns[3].metric("ROE", f"{float(row['ROE (%)']):.1f}%")


def show_station(symbol: str, bars: pd.DataFrame, base, neckline: float | None, board: pd.DataFrame) -> None:
    st.subheader(symbol)
    show_symbol_header(symbol, bars, board)
    show_charts(symbol, bars, neckline)
    commentary(symbol, bars)
    if base is not None:
        show_support(base)
    with st.expander("Định giá và mẫu hình", expanded=False):
        show_patterns(symbol, bars)
        show_valuation(symbol)


def open_page() -> None:
    try:
        board = read_cache()
    except Exception as error:
        st.error(f"Không đọc được cache: {error}")
        return
    capital, risk_pct, filters = render_sidebar()
    universe = read_universe()
    source = universe if universe is not None else board
    shown = apply_filter(
        source,
        filters["min_roe_pct"],
        filters["min_volume"],
        filters["min_rs"],
        filters["top_n"],
    )
    loosened = filters["min_roe_pct"] < MIN_ROE * 100 or filters["min_volume"] < MIN_AVG_VOLUME
    if universe is None and loosened:
        filter_note = (
            f"Đang hiện {len(shown)} mã từ Top 20 đã lưu. "
            "Hạ ROE dưới 12% hoặc khối lượng dưới 100.000 cần bấm Quét để có đủ mã."
        )
    else:
        filter_note = (
            f"Đang hiện {len(shown)} mã. ROE ≥ {filters['min_roe_pct']:.1f}%, "
            f"KL ≥ {filters['min_volume']:,.0f}"
            + ("" if filters["min_rs"] <= RS_FILTER_OFF else f", RS ≥ {filters['min_rs']:.0f}%")
            + f", tối đa {filters['top_n']} mã."
        )
    page = st.segmented_control(
        "Trang",
        [
            "Tổng quan",
            "Trạm Trading",
            "Bộ lọc tín hiệu",
            "Danh mục",
            "Tin tức / Bài viết",
        ],
        default="Tổng quan",
        key="open_page",
    )
    if page in (None, "Tổng quan", "Dashboard"):
        from ui.overview_page import show_overview

        show_overview()
        with st.expander("Top dẫn dắt đã lưu", expanded=False):
            show_dashboard(shown, filter_note)
        return
    if page == "Danh mục":
        from ui.portfolio_page import show_portfolio
        from ui.watchlists_page import show_watchlists

        section = st.segmented_control(
            "Mục",
            ["Watchlist", "Vị thế"],
            default="Watchlist",
            key="portfolio_section",
        )
        if section == "Vị thế":
            show_portfolio()
        else:
            show_watchlists()
        return
    if page == "Tin tức / Bài viết":
        from ui.alerts_page import show_alerts
        from ui.posts_page import show_news_and_posts

        show_alerts()
        show_news_and_posts()
        return
    if page == "Bộ lọc tín hiệu":
        from ui.filters_page import show_filters

        show_filters()
        return
    from ui.trading_desk import show_trading_desk

    show_trading_desk(capital)
    prepared = prepare(shown)
    if prepared is None:
        return
    symbol, bars, base, neckline = prepared
    show_position(symbol, float(bars["close"].iloc[-1]), bars, capital, risk_pct)
    show_station(symbol, bars, base, neckline, shown)
    if st.checkbox("Mở phần đọc vị nến và CANSLIM", value=False):
        show_candle_lesson(symbol, bars)
        show_canslim(symbol, bars)
