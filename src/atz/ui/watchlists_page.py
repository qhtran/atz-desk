"""Tab Watchlist trong Danh mục: ngành F3 (mentor) + danh mục riêng của user."""

from __future__ import annotations

from datetime import date
from typing import Callable

import streamlit as st

from analysis.f3_alerts import alert_column_for_bars
from config import BARS_DIR, UNIVERSE
from datasource.f3_themes import load_f3_sector_themes
from datasource.live_quotes import load_live_prices_thousands
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
from engine.runner import load_symbol_csv
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


def _alert_for_symbol(symbol: str) -> str:
    """Cột Cảnh báo F3 — khung ngày; thiếu bars → —."""
    try:
        bars = load_symbol_csv(BARS_DIR, symbol)
    except Exception:
        return "—"
    return alert_column_for_bars(symbol, bars, session_date=date.today())


def _ohlcv_last_close(symbol: str) -> float | None:
    """Close nến ngày cuối (nghìn đồng). Thiếu file → None."""
    try:
        bars = load_symbol_csv(BARS_DIR, symbol)
    except Exception:
        return None
    if bars is None or getattr(bars, "empty", True):
        return None
    try:
        return round(float(bars["close"].iloc[-1]), 2)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return None


def _format_price_cell(value: float | None) -> str | float:
    """Giá nghìn đồng 2 chữ số; miss → — (chuỗi để không lệch NumberColumn)."""
    if value is None:
        return "—"
    return round(float(value), 2)


def build_wl_symbol_rows(
    symbols: list[str],
    volumes: dict[str, float] | None = None,
    *,
    with_alerts: bool = False,
    live_prices: dict[str, float] | None = None,
    alert_fn: Callable[[str], str] | None = None,
    ohlcv_fn: Callable[[str], float | None] | None = None,
) -> tuple[list[dict[str, object]], int, int]:
    """Build wl_rows. Khi with_alerts: Mã | Giá | [KL] | Cảnh báo.

    Returns (rows, redis_hits, priced_count). Giá = Redis RT; miss → OHLCV close; cả hai miss → —.
    """
    cleaned = [str(s).strip().upper() for s in symbols if str(s).strip()]
    prices = live_prices
    if with_alerts and prices is None:
        prices = load_live_prices_thousands(cleaned)
    prices = prices or {}
    alert = alert_fn or _alert_for_symbol
    ohlcv = ohlcv_fn or _ohlcv_last_close

    rows: list[dict[str, object]] = []
    redis_hits = 0
    priced = 0
    for symbol in cleaned:
        row: dict[str, object] = {"Mã": symbol}
        if with_alerts:
            live = prices.get(symbol)
            if live is not None:
                cell = _format_price_cell(float(live))
                redis_hits += 1
                priced += 1
            else:
                fb = ohlcv(symbol)
                cell = _format_price_cell(fb)
                if fb is not None:
                    priced += 1
            row["Giá"] = cell
        if volumes and symbol in volumes:
            row["KL TB 10 phiên"] = volumes[symbol]
        if with_alerts:
            row["Cảnh báo"] = alert(symbol)
        rows.append(row)
    return rows, redis_hits, priced


def _show_symbol_table(
    symbols: list[str],
    volumes: dict[str, float] | None = None,
    *,
    with_alerts: bool = False,
) -> None:
    if not symbols:
        st.caption("Chưa có mã.")
        return
    rows, redis_hits, priced = build_wl_symbol_rows(
        symbols, volumes, with_alerts=with_alerts
    )
    render_data_table(
        rows,
        variant="analytical",
        pin="Mã",
        key="wl_rows",
        alt="Danh sách mã trong watchlist",
        column_config=(
            {"Giá": st.column_config.TextColumn("Giá", width="small")}
            if with_alerts
            else None
        ),
    )
    if with_alerts:
        total = len(rows)
        if redis_hits:
            src = f"Redis quote RT {redis_hits}/{total}"
        elif priced:
            src = f"OHLCV fallback {priced}/{total}"
        else:
            src = "không có quote/OHLCV"
        st.caption(f"Giá: {src} (nghìn đồng). Miss → —.")


def _f3_sector_section(sectors: list[dict]) -> None:
    st.subheader("Danh mục theo ngành (F3)")
    st.caption(
        "Seed mentor F3 — cột **Giá** (Redis RT) + **Cảnh báo** theo nến ngày "
        "(MA/BB/mây/đáy-đỉnh). Chỉ UI decision-support; không đặt lệnh. "
        "Thiếu ≥25 nến ngày → —."
    )
    names = [item["name"] for item in sectors]
    chosen = st.selectbox("Ngành", names, key="wl_f3_sector_pick")
    sector = next(item for item in sectors if item["name"] == chosen)
    _show_symbol_table(sector["symbols"], with_alerts=True)
    left, right = st.columns(2)
    if left.button("Dùng cho Bộ lọc tín hiệu", key="wl_f3_to_filter", width="stretch"):
        _send_to_filter(sector["symbols"], sector["name"])
    if right.button("Đưa vào Trạm Trading", key="wl_f3_to_desk", width="stretch"):
        _send_to_desk(sector["symbols"], sector["name"])


def _legacy_sector_section() -> None:
    st.subheader("Danh mục theo ngành")
    industries = load_industry_map()
    if not industries:
        st.info(
            "Chưa có seed F3 và chưa có dữ liệu ngành ICB. "
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
        "Fallback ICB: mỗi ngành tối đa 8 mã trong danh sách quét, ưu tiên KL TB 10 phiên. "
        "Chỉ đọc nến đã lưu, không gọi mạng."
    )
    names = [item["name"] for item in sectors]
    chosen = st.selectbox("Ngành", names, key="wl_sector_pick")
    sector = next(item for item in sectors if item["name"] == chosen)
    _show_symbol_table(sector["symbols"], sector.get("volumes"), with_alerts=True)
    left, right = st.columns(2)
    if left.button("Dùng cho Bộ lọc tín hiệu", key="wl_sector_to_filter", width="stretch"):
        _send_to_filter(sector["symbols"], sector["name"])
    if right.button("Đưa vào Trạm Trading", key="wl_sector_to_desk", width="stretch"):
        _send_to_desk(sector["symbols"], sector["name"])


def _sector_section() -> None:
    f3 = load_f3_sector_themes()
    if f3:
        _f3_sector_section(f3)
        return
    _legacy_sector_section()


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
