"""Không gian Trading — Vốn & Risk · Filter defaults · Pin · Lưu toàn bộ."""

from __future__ import annotations

import streamlit as st

from config import CAPITAL_STEP, RISK_MAX, RISK_MIN, RS_FILTER_OFF, UNIVERSE
from datasource.capital_ledger import CapitalLedger
from datasource.user_trading import (
    FilterDefaults,
    load_filter_defaults,
    load_pinned_symbols,
    load_user_trading,
    persist_workspace,
)
from engine.identity import current_username


def _pins_from_text(text: str) -> list[str]:
    parts = [p.strip() for p in str(text or "").replace(";", ",").split(",")]
    return [p for p in parts if p]


def show_trading_workspace() -> None:
    username = current_username()
    trading = load_user_trading(username)
    prefs = load_filter_defaults(username)
    pins = load_pinned_symbols(username)

    st.subheader("Không gian Trading")
    st.caption(
        f"Cấu hình theo user `{trading.username}` (SQLite). "
        "Sidebar chỉ xem — sửa và lưu tại đây."
    )

    with st.form("trading_workspace_form", clear_on_submit=False):
        st.markdown("#### Vốn & rủi ro")
        c1, c2, c3 = st.columns(3)
        initial = c1.number_input(
            "Vốn rót lần đầu (VND)",
            min_value=0.0,
            value=float(trading.ledger.initial),
            step=float(CAPITAL_STEP),
        )
        additional = c2.number_input(
            "Vốn bổ sung (VND)",
            min_value=0.0,
            value=float(trading.ledger.additional),
            step=float(CAPITAL_STEP),
        )
        withdrawn = c3.number_input(
            "Vốn đã rút ra (VND)",
            min_value=0.0,
            value=float(trading.ledger.withdrawn),
            step=float(CAPITAL_STEP),
        )
        risk_pct = st.slider(
            "Mức rủi ro tối đa trên tổng vốn (%)",
            RISK_MIN,
            RISK_MAX,
            value=int(trading.risk_tolerance_pct),
        )

        st.markdown("#### Bộ lọc mặc định")
        f1, f2 = st.columns(2)
        min_roe_pct = f1.number_input(
            "ROE tối thiểu (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(prefs.min_roe_pct),
            step=0.5,
        )
        min_volume = f2.number_input(
            "KLGD TB 20 phiên tối thiểu",
            min_value=0.0,
            value=float(prefs.min_volume),
            step=10_000.0,
        )
        f3, f4 = st.columns(2)
        min_rs = f3.number_input(
            "RS 3 tháng tối thiểu (%)",
            min_value=float(RS_FILTER_OFF),
            max_value=200.0,
            value=float(prefs.min_rs),
            step=1.0,
            help="Mức sàn không cắt thêm. Tăng để chỉ giữ mã mạnh hơn.",
        )
        top_n = f4.slider(
            "Số mã hiển thị mặc định",
            min_value=5,
            max_value=len(UNIVERSE),
            value=int(prefs.top_n),
        )

        st.markdown("#### RSI / MACD (ưu tiên filter)")
        r1, r2 = st.columns(2)
        rsi_oversold = r1.number_input(
            "RSI oversold",
            min_value=0,
            max_value=100,
            value=int(prefs.rsi_oversold),
            step=1,
        )
        rsi_overbought = r2.number_input(
            "RSI overbought",
            min_value=0,
            max_value=100,
            value=int(prefs.rsi_overbought),
            step=1,
        )
        m1, m2, m3 = st.columns(3)
        macd_fast = m1.number_input("MACD fast", min_value=2, value=int(prefs.macd_fast), step=1)
        macd_slow = m2.number_input("MACD slow", min_value=3, value=int(prefs.macd_slow), step=1)
        macd_signal = m3.number_input(
            "MACD signal", min_value=2, value=int(prefs.macd_signal), step=1
        )

        st.markdown("#### Ghim mã")
        pins_text = st.text_input(
            "Danh sách ghim (cách nhau bởi dấu phẩy)",
            value=", ".join(pins),
            help="Ví dụ: FPT, VIC, VNM — tối đa 40 mã.",
        )

        saved = st.form_submit_button("Lưu toàn bộ", width="stretch", type="primary")

    if not saved:
        return

    clean = persist_workspace(
        username,
        CapitalLedger(initial=initial, additional=additional, withdrawn=withdrawn),
        int(risk_pct),
        FilterDefaults(
            min_roe_pct=float(min_roe_pct),
            min_volume=float(min_volume),
            min_rs=float(min_rs),
            top_n=int(top_n),
            rsi_oversold=int(rsi_oversold),
            rsi_overbought=int(rsi_overbought),
            macd_fast=int(macd_fast),
            macd_slow=int(macd_slow),
            macd_signal=int(macd_signal),
        ),
        _pins_from_text(pins_text),
    )
    # Đồng bộ widget sidebar (nếu đã khởi tạo trong session)
    st.session_state["sidebar_min_roe"] = float(clean.min_roe_pct)
    st.session_state["sidebar_min_volume"] = float(clean.min_volume)
    st.session_state["sidebar_min_rs"] = float(clean.min_rs)
    st.session_state["sidebar_top_n"] = int(clean.top_n)
    st.session_state["sidebar_risk"] = int(risk_pct)
    st.success("Đã lưu Không gian Trading (vốn, rủi ro, bộ lọc, ghim).")
    st.rerun()
