"""Tab Watchlist trong Danh mục: ngành mặc định + danh mục riêng của user."""

from __future__ import annotations

import streamlit as st

from config import UNIVERSE
from datasource.watchlists import (
    add_symbol,
    create_watchlist,
    default_sector_watchlists,
    delete_watchlist,
    load_industry_map,
    load_user_watchlists,
    remove_symbol,
)
from engine.identity import current_username
from ui.components import render_data_table


def _send_to_filter(symbols: list[str], label: str) -> None:
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    st.session_state["filter_symbols"] = cleaned
    st.session_state["open_page"] = "Bộ lọc tín hiệu"
    st.session_state["filter_mode"] = "Lọc tự do"
    st.success(f"Đã gửi {len(cleaned)} mã từ «{label}» sang Bộ lọc tín hiệu.")
    st.rerun()


def _send_to_desk(symbols: list[str], label: str) -> None:
    from ui.trading_desk import adopt_from_signal

    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    added = 0
    existed = 0
    for symbol in cleaned:
        status = adopt_from_signal(symbol, f"Watchlist · {label}")
        if status == "added":
            added += 1
        elif status == "exists":
            existed += 1
    st.session_state["open_page"] = "Trạm Trading"
    st.success(f"Đã đưa {added} mã mới vào Trạm Trading" + (f" ({existed} mã đã có)." if existed else "."))
    st.rerun()


def _show_symbol_table(symbols: list[str], volumes: dict[str, float] | None = None) -> None:
    if not symbols:
        st.caption("Chưa có mã.")
        return
    rows = []
    for symbol in symbols:
        row = {"Mã": symbol}
        if volumes and symbol in volumes:
            row["KL TB 10 phiên"] = volumes[symbol]
        rows.append(row)
    render_data_table(
        rows, variant="analytical", pin="Mã", key="wl_rows", alt="Danh sách mã trong watchlist"
    )


def _sector_section() -> None:
    st.subheader("Danh mục theo ngành")
    industries = load_industry_map()
    if not industries:
        st.info(
            "Chưa có dữ liệu ngành. "
            "Danh mục mặc định theo ngành sẽ hiện khi có dữ liệu. "
            "Bạn vẫn tạo được danh mục riêng bên dưới."
        )
        return
    try:
        sectors = default_sector_watchlists()
    except Exception as error:
        st.warning(f"Không lập được danh mục ngành: {error}")
        return
    if not sectors:
        st.info("Không có mã nào trong danh sách quét khớp ngành đã lưu.")
        return
    st.caption(
        "Mỗi ngành lấy tối đa 8 mã trong danh sách quét, ưu tiên KL trung bình 10 phiên cao. "
        "Chỉ đọc nến đã lưu, không gọi mạng."
    )
    names = [item["name"] for item in sectors]
    chosen = st.selectbox("Ngành", names, key="wl_sector_pick")
    sector = next(item for item in sectors if item["name"] == chosen)
    _show_symbol_table(sector["symbols"], sector.get("volumes"))
    left, right = st.columns(2)
    if left.button("Dùng cho Bộ lọc tín hiệu", key="wl_sector_to_filter", width="stretch"):
        _send_to_filter(sector["symbols"], sector["name"])
    if right.button("Đưa vào Trạm Trading", key="wl_sector_to_desk", width="stretch"):
        _send_to_desk(sector["symbols"], sector["name"])


def _custom_section(username: str) -> None:
    st.subheader("Danh mục của tôi")
    st.caption(f"User «{username}». Danh sách được lưu theo tài khoản.")
    lists = load_user_watchlists(username)

    with st.form("wl_create"):
        name = st.text_input("Tên danh mục mới", placeholder="Ví dụ: Theo dõi tuần")
        seed = st.multiselect("Thêm mã sẵn (tuỳ chọn)", options=list(UNIVERSE))
        created = st.form_submit_button("Tạo danh mục")
    if created:
        try:
            create_watchlist(username, name, seed)
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()

    if not lists:
        st.info("Chưa có danh mục riêng. Tạo một danh mục ở form trên.")
        return

    labels = {item["id"]: f"{item['name']} ({len(item['symbols'])} mã)" for item in lists}
    picked_id = st.selectbox(
        "Chọn danh mục",
        options=list(labels),
        format_func=lambda key: labels[key],
        key="wl_custom_pick",
    )
    current = next(item for item in lists if item["id"] == picked_id)
    _show_symbol_table(current["symbols"])

    add_col, remove_col = st.columns(2)
    with add_col:
        with st.form("wl_add_symbol"):
            new_symbol = st.text_input("Thêm mã", placeholder="FPT")
            add_clicked = st.form_submit_button("Thêm")
        if add_clicked:
            try:
                if add_symbol(username, picked_id, new_symbol) is None:
                    st.error("Không tìm thấy danh mục.")
                else:
                    st.rerun()
            except ValueError as error:
                st.error(str(error))
    with remove_col:
        if current["symbols"]:
            drop = st.selectbox("Xóa mã", current["symbols"], key="wl_drop_symbol")
            if st.button("Xóa mã đã chọn", key="wl_remove_symbol"):
                remove_symbol(username, picked_id, drop)
                st.rerun()

    actions = st.columns(3)
    if actions[0].button("Dùng cho Bộ lọc", key="wl_custom_to_filter", width="stretch"):
        _send_to_filter(current["symbols"], current["name"])
    if actions[1].button("Đưa vào Trạm Trading", key="wl_custom_to_desk", width="stretch"):
        _send_to_desk(current["symbols"], current["name"])
    if actions[2].button("Xóa danh mục này", key="wl_delete_list", width="stretch"):
        delete_watchlist(username, picked_id)
        st.rerun()


def show_watchlists() -> None:
    username = current_username()
    _sector_section()
    st.divider()
    _custom_section(username)
