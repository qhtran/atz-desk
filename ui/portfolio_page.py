"""Tab Danh mục: vị thế, lãi lỗ, nhật ký và số phần đã giải ngân."""

from __future__ import annotations

from datetime import date

import streamlit as st

from config import CAPITAL_TRANCHES
from datasource.portfolio import (
    add_journal,
    add_position,
    delete_journal,
    delete_position,
    last_close,
    list_journal,
    list_positions,
    profit_vnd,
    tranche_usage,
)


def _positions_view(positions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, item in positions.iterrows():
        price = last_close(str(item["Mã"]))
        gain = profit_vnd(item["Giá mua"], item["Khối lượng"], price)
        rows.append(
            {
                "Mã": item["Mã"],
                "Giá mua": item["Giá mua"],
                "Giá hiện tại": price,
                "Khối lượng": item["Khối lượng"],
                "Ngày mua": item["Ngày mua"],
                "Phần đã giải ngân": item["Phần đã giải ngân"],
                "Lãi/lỗ (VND)": gain,
            }
        )
    return pd.DataFrame(rows)


def show_portfolio() -> None:
    st.subheader("Vị thế đang nắm")
    st.caption(
        f"Giá nghìn đồng. Lãi/lỗ nhân {1000:,} ra đồng, lấy giá đóng cửa trong data/ohlcv nếu đã có. "
        f"Mỗi mã giải ngân tối đa {CAPITAL_TRANCHES} phần."
    )
    positions = list_positions()
    if positions.empty:
        st.info("Chưa có vị thế.")
    else:
        shown = _positions_view(positions)
        st.dataframe(
            shown.style.format(
                {
                    "Giá mua": "{:.2f}",
                    "Giá hiện tại": "{:.2f}",
                    "Khối lượng": "{:,.0f}",
                    "Lãi/lỗ (VND)": "{:,.0f}",
                },
                na_rep="—",
            ),
            hide_index=True,
            width="stretch",
            alt="Danh sách vị thế và lãi lỗ",
        )
        usage = tranche_usage(positions)
        st.markdown("**Giải ngân theo mã**")
        st.dataframe(usage, hide_index=True, width="stretch", alt="Số phần đã giải ngân theo mã")
        over = usage.loc[usage["Phần đã giải ngân"] > CAPITAL_TRANCHES, "Mã"]
        if not over.empty:
            st.warning(f"Vượt {CAPITAL_TRANCHES} phần: {', '.join(over.astype(str))}.")

    with st.form("add_position"):
        st.markdown("**Thêm vị thế**")
        columns = st.columns(5)
        symbol = columns[0].text_input("Mã", value="POW")
        buy_price = columns[1].number_input("Giá mua", min_value=0.0, value=10.0, step=0.05)
        shares = columns[2].number_input("Khối lượng", min_value=0.0, value=100.0, step=10.0)
        buy_date = columns[3].date_input("Ngày mua", value=date.today())
        tranches = columns[4].number_input("Phần đã giải ngân", min_value=1, max_value=CAPITAL_TRANCHES, value=1)
        submitted = st.form_submit_button("Lưu vị thế")
    if submitted:
        try:
            add_position(symbol, float(buy_price), float(shares), buy_date.isoformat(), int(tranches))
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()

    if not positions.empty:
        choice = st.selectbox("Xóa vị thế", positions["id"].astype(str) + " · " + positions["Mã"].astype(str))
        if st.button("Xóa vị thế đã chọn"):
            delete_position(choice.split(" · ", maxsplit=1)[0])
            st.rerun()

    st.subheader("Nhật ký")
    journal = list_journal()
    symbol_filter = st.text_input("Lọc nhật ký theo mã", value="", placeholder="Để trống để xem mọi mã")
    shown_notes = journal
    code = symbol_filter.strip().upper()
    if code and not journal.empty:
        shown_notes = journal.loc[journal["Mã"].astype(str) == code]
    if shown_notes.empty:
        st.info("Chưa có ghi chú khớp bộ lọc.")
    else:
        st.dataframe(
            shown_notes.drop(columns=["id"]),
            hide_index=True,
            width="stretch",
            alt="Nhật ký mua bán theo thời gian",
        )
    with st.form("add_journal"):
        st.markdown("**Ghi nhật ký**")
        note_columns = st.columns(3)
        note_symbol = note_columns[0].text_input("Mã nhật ký", value="POW")
        side = note_columns[1].selectbox("Chiều", ["Mua", "Bán"])
        note = st.text_area("Lý do và ghi chú", placeholder="Vì sao mua hoặc bán")
        note_submitted = st.form_submit_button("Lưu nhật ký")
    if note_submitted:
        try:
            add_journal(note_symbol, side, note)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()
    if not journal.empty:
        note_choice = st.selectbox(
            "Xóa nhật ký",
            journal["id"].astype(str) + " · " + journal["Mã"].astype(str) + " · " + journal["Thời điểm"].astype(str),
        )
        if st.button("Xóa nhật ký đã chọn"):
            delete_journal(note_choice.split(" · ", maxsplit=1)[0])
            st.rerun()
