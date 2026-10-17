"""Sidebar «Tổng quan vị thế của bạn» (F1 mục 2 MVP).

Giá ưu tiên Redis quote:{symbol} (đổi sang nghìn đồng); thiếu thì OHLCV đóng cửa.
GTCK ước lượng theo vốn phân bổ trên desk khi chưa có KL.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.session import market_session
from config import (
    CAPITAL_STEP,
    CAPITAL_TRANCHES,
    RISK_MAX,
    RISK_MIN,
)
from datasource.capital_ledger import CapitalLedger, nav_breakdown
from datasource.live_quotes import load_live_prices_thousands
from datasource.user_trading import load_user_trading, persist_capital_and_risk
from engine.identity import current_username
from ui.trading_desk import _bars, _last_close, _optional, load_desk

ALERT_BANDS = (5.0, 8.0, 10.0)
NEAR_ZONE_PCT = 2.0


def position_alert(
    buy: float | None,
    current: float | None,
    support: float | None = None,
    resistance: float | None = None,
) -> str:
    """Ưu tiên hỗ trợ/kháng cự gần, rồi mốc ±5/8/10% so với giá mua."""
    if current is None:
        return "Chưa có giá"
    notes: list[str] = []
    if support is not None and support > 0:
        gap = (current - support) / support * 100
        if abs(gap) <= NEAR_ZONE_PCT:
            notes.append("Gần hỗ trợ")
        elif current < support:
            notes.append("Dưới hỗ trợ")
    if resistance is not None and resistance > 0:
        gap = (resistance - current) / resistance * 100
        if abs(gap) <= NEAR_ZONE_PCT:
            notes.append("Gần kháng cự")
        elif current > resistance:
            notes.append("Vượt kháng cự")
    if buy is not None and buy > 0:
        change = (current - buy) / buy * 100
        hit = None
        for band in ALERT_BANDS:
            if abs(change) + 0.05 >= band:
                hit = band
        if hit is not None:
            sign = "+" if change >= 0 else "−"
            notes.append(f"{sign}{hit:.0f}%")
    return " · ".join(notes) if notes else "—"


def desk_position_rows(
    store: pd.DataFrame,
    capital: float,
    live_prices: dict[str, float] | None = None,
) -> list[dict]:
    """Mỗi mã desk → giá / cảnh báo / vốn phân bổ ước lượng.

    live_prices: SYMBOL → nghìn đồng (từ Redis). None → tự MGET; {} → chỉ OHLCV.
    """
    quarter = capital / CAPITAL_TRANCHES if capital > 0 else 0.0
    symbols: list[str] = []
    for _, item in store.iterrows():
        symbol = str(item["Mã"]).strip().upper()
        if symbol and symbol != "NAN":
            symbols.append(symbol)
    if live_prices is None:
        live_prices = load_live_prices_thousands(symbols)

    rows: list[dict] = []
    for _, item in store.iterrows():
        symbol = str(item["Mã"]).strip().upper()
        if not symbol or symbol == "NAN":
            continue
        frame = _bars(symbol)
        ohlcv = _last_close(frame)
        current = live_prices.get(symbol)
        source = "redis"
        if current is None:
            current = ohlcv
            source = "ohlcv"
        buy = _optional(item["Giá mua"])
        support = _optional(item["Vùng hỗ trợ"])
        resistance = _optional(item["Vùng kháng cự"])
        allocated = _optional(item["Thăm dò 1/4 NAV"]) if "Thăm dò 1/4 NAV" in item.index else None
        if allocated is None:
            allocated = quarter
        cost = float(allocated) if allocated and allocated > 0 else 0.0
        if buy is not None and buy > 0 and current is not None and cost > 0:
            mkt = cost * (current / buy)
            pnl = mkt - cost
            pnl_pct = (current - buy) / buy * 100
        else:
            mkt = cost
            pnl = 0.0
            pnl_pct = 0.0 if buy is None or current is None or not buy else (current - buy) / buy * 100
        rows.append(
            {
                "Mã": symbol,
                "Giá mua": buy,
                "Giá hiện tại": current,
                "Cảnh báo": position_alert(buy, current, support, resistance),
                "cost": cost,
                "mkt": mkt,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "price_source": source,
            }
        )
    return rows


def _money(value: float) -> str:
    return f"{value:,.0f}"


def render_portfolio_overview() -> tuple[float, float]:
    """Vẽ khối tổng quan vị thế. Trả (capital/NAV dùng sizing, risk_pct)."""
    st.header("Tổng quan vị thế của bạn")
    status, clock = market_session()
    username = current_username()
    trading = load_user_trading(username)
    st.caption(f"{status} · Giờ HN {clock} · User `{trading.username}` (SQLite)")

    saved = trading.ledger
    if "sidebar_risk" not in st.session_state:
        st.session_state["sidebar_risk"] = int(trading.risk_tolerance_pct)

    with st.expander("Sổ vốn (nạp / rút)", expanded=False):
        initial = st.number_input(
            "Vốn rót lần đầu (VND)",
            min_value=0.0,
            value=float(saved.initial),
            step=float(CAPITAL_STEP),
            key="cap_initial",
        )
        additional = st.number_input(
            "Vốn bổ sung (VND)",
            min_value=0.0,
            value=float(saved.additional),
            step=float(CAPITAL_STEP),
            key="cap_additional",
        )
        withdrawn = st.number_input(
            "Vốn đã rút ra (VND)",
            min_value=0.0,
            value=float(saved.withdrawn),
            step=float(CAPITAL_STEP),
            key="cap_withdrawn",
        )
        if st.button("Lưu sổ vốn & rủi ro", width="stretch", key="cap_save"):
            risk_now = int(st.session_state.get("sidebar_risk", trading.risk_tolerance_pct))
            persist_capital_and_risk(
                username,
                CapitalLedger(initial=initial, additional=additional, withdrawn=withdrawn),
                risk_now,
            )
            st.success("Đã lưu sổ vốn & rủi ro (SQLite theo user).")
            st.rerun()
        ledger = CapitalLedger(initial=initial, additional=additional, withdrawn=withdrawn)

    store = load_desk()
    positions = desk_position_rows(store, ledger.total)
    cost = sum(float(row["cost"]) for row in positions)
    mkt = sum(float(row["mkt"]) for row in positions)
    snap = nav_breakdown(ledger, cost, mkt)

    st.metric("Tổng vốn hiện tại", _money(snap["total_capital"]))
    st.metric("Giá trị chứng khoán", _money(snap["securities_mkt"]))
    st.metric("Tiền mặt", _money(snap["cash"]))
    st.metric("Tài sản ròng (NAV)", _money(snap["nav"]), delta=int(round(snap["pnl"])))

    st.subheader("Vị thế hiện tại")
    if not positions:
        st.caption("Chưa có mã trên Trạm Trading.")
    else:
        view = pd.DataFrame(
            [
                {
                    "Mã": row["Mã"],
                    "Giá mua": row["Giá mua"],
                    "Giá HT": row["Giá hiện tại"],
                    "Cảnh báo": row["Cảnh báo"],
                }
                for row in positions
            ]
        )
        st.dataframe(
            view,
            hide_index=True,
            width="stretch",
            alt="Vị thế sidebar: mã, giá mua, giá hiện tại, cảnh báo",
            column_config={
                "Giá mua": st.column_config.NumberColumn(format="%.2f"),
                "Giá HT": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        hits = sum(1 for row in positions if row.get("price_source") == "redis")
        src = f"Redis {hits}/{len(positions)}" if hits else "OHLCV fallback"
        st.caption(f"Giá HT: {src} (nghìn đồng). Tham chiếu: https://rtboard.hsx.vn/")

        chart = pd.DataFrame(
            {"Mã": [row["Mã"] for row in positions], "Lãi/lỗ (VND)": [row["pnl"] for row in positions]}
        ).set_index("Mã")
        st.bar_chart(chart, alt="Lãi lỗ ước lượng từng mã trên NAV phân bổ")
        st.caption("Lãi/lỗ ước lượng theo vốn phân bổ (1/4 NAV hoặc ô Thăm dò trên desk).")

    with st.expander("Phiên và mức rủi ro (sizing)", expanded=False):
        st.caption(f"Sáng 9:00–11:30, chiều 13:00–14:45. NAV sizing: {_money(snap['nav'])} VND.")
        risk_pct = st.slider(
            "Mức rủi ro tối đa trên tổng vốn (%)",
            RISK_MIN,
            RISK_MAX,
            key="sidebar_risk",
        )
        if st.button("Lưu mức rủi ro", width="stretch", key="risk_save"):
            persist_capital_and_risk(username, ledger, int(risk_pct))
            st.success("Đã lưu mức rủi ro.")
            st.rerun()
        probe = snap["nav"] / CAPITAL_TRANCHES if snap["nav"] > 0 else 0.0
        st.markdown(f"Lệnh 1 dò đường (1/{CAPITAL_TRANCHES} NAV): {_money(probe)} VND")

    return float(snap["nav"]), float(risk_pct)
