"""Trang Bộ lọc tín hiệu. Form sinh từ metadata, không hardcode tham số."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from config import UNIVERSE
from engine.exchange import export_user, import_user
from engine.identity import current_username
from engine.notify import BrevoSender, maybe_notify
from engine.runner import load_frames_for_run, run_frames
from filters import load_registry
from ui.components import render_data_table
from filters.base import ParamSpec
from storage.db import open_signals
from storage.repository import (
    delete_filter_configs,
    ensure_user,
    get_user,
    list_filter_configs,
    save_filter_config,
    set_user_settings,
)


def _field(filter_name: str, param: ParamSpec, current: dict) -> object:
    key = f"filter_{filter_name}_{param.name}"
    value = current.get(param.name, param.default)
    if param.kind == "int":
        return int(
            st.number_input(
                param.label,
                min_value=int(param.min or 0),
                max_value=int(param.max or 10_000),
                value=int(value),
                step=1,
                key=key,
            )
        )
    if param.kind == "float":
        return float(
            st.number_input(
                param.label,
                min_value=float(param.min if param.min is not None else 0.0),
                max_value=float(param.max if param.max is not None else 10_000.0),
                value=float(value),
                step=0.1,
                key=key,
            )
        )
    if param.kind == "bool":
        return bool(st.checkbox(param.label, value=bool(value), key=key))
    if param.kind == "choice" and param.choices:
        options = list(param.choices)
        selected = value if value in options else options[0]
        return st.selectbox(param.label, options, index=options.index(selected), key=key)
    return st.text_input(param.label, value="" if value is None else str(value), key=key)


def _save(conn, user_id: int, names: list[str], chosen: dict[str, dict]) -> None:
    delete_filter_configs(conn, user_id)
    for index, name in enumerate(names):
        save_filter_config(conn, user_id, name, chosen[name], True, index)


def _show_criteria_catalog() -> None:
    from ui.filter_criteria import criteria_board

    with st.expander("Tiêu chí lọc (catalog F1)", expanded=False):
        render_data_table(
            criteria_board(),
            variant="analytical",
            pin=None,
            key="flt_criteria",
            alt="Bảng tiêu chí lọc kỹ thuật và mẫu hình theo checklist F1",
        )
        st.caption(
            "Catalog theo mentor F1. Chọn bộ lọc tương ứng bên dưới để chạy. "
            "Bollinger / Ichimoku / phần II chờ mô tả bổ sung."
        )


def show_filters() -> None:
    st.subheader("Bộ lọc tín hiệu")
    _show_criteria_catalog()
    mode = st.segmented_control(
        "Chế độ",
        ["Lọc tự do", "Top 5 mỗi ngành"],
        default="Lọc tự do",
        key="filter_mode",
    )
    if mode == "Top 5 mỗi ngành":
        from ui.industry_top import show_industry_top

        show_industry_top()
        return
    st.caption(f"User {current_username()}. Cấu hình được lưu theo tài khoản.")
    registry = load_registry()
    labels = {name: module.FILTER.label for name, module in registry.items()}
    conn = open_signals()
    try:
        user_id = ensure_user(conn, current_username())
        user = get_user(conn, user_id)
        saved = {row["filter_name"]: row for row in list_filter_configs(conn, user_id)}
        default_names = [name for name in saved if name in registry and saved[name]["enabled"]]
        # Ô chọn mã đặt đầu trang, full width: luôn thấy trên điện thoại.
        preset = [
            str(item).strip().upper()
            for item in st.session_state.get("filter_symbols", [])
            if str(item).strip()
        ]
        preset = [item for item in preset if item in UNIVERSE]
        symbols = st.multiselect(
            "Mã cần lọc",
            options=list(UNIVERSE),
            default=preset,
            placeholder="Chọn mã hoặc gửi từ Danh mục",
        )
        st.caption(f"Đã chọn {len(symbols)} mã.")
        names = st.multiselect(
            "Bộ lọc đang dùng",
            options=sorted(registry),
            default=default_names,
            format_func=lambda name: labels.get(name, name),
        )
        chosen: dict[str, dict] = {}
        for name in names:
            spec = registry[name].FILTER
            current = (saved.get(name) or {}).get("parameters") or {}
            st.markdown(f"**{spec.label}**")
            st.caption(spec.description)
            params = {param.name: _field(name, param, current) for param in spec.params}
            chosen[name] = params

        settings = user["cai_dat_chung"] if user else {}
        with st.expander("Email thông báo"):
            email = st.text_input("Email nhận", value=user["email_nhan_thong_bao"] or "")
            email_on = st.checkbox("Bật nhận mail", value=bool(settings.get("email_bat")))
            kinds = st.multiselect(
                "Loại tín hiệu",
                ["mua", "ban", "giu", "cho"],
                default=list(settings.get("loai_nhan") or ["mua", "ban"]),
            )
        columns = st.columns(3)
        save_clicked = columns[0].button("Lưu cấu hình", width="stretch")
        run_clicked = columns[1].button("Chạy lọc", width="stretch")
        payload = export_user(conn, user_id)
        columns[2].download_button(
            "Tải JSON",
            json.dumps(payload, ensure_ascii=False, indent=2),
            file_name="bo_loc.json",
            mime="application/json",
            width="stretch",
        )
        if save_clicked or run_clicked:
            _save(conn, user_id, names, chosen)
            set_user_settings(
                conn,
                user_id,
                {"email_bat": email_on, "loai_nhan": kinds, "che_do_gui": "ngay"},
                email.strip() or None,
            )
        if save_clicked:
            st.success("Đã lưu cấu hình của user này.")
        if run_clicked:
            if not symbols:
                st.warning("Chọn ít nhất một mã.")
            else:
                configs = [
                    {"filter_name": name, "parameters": chosen[name], "enabled": 1}
                    for name in names
                ]
                kinds = {name for name in ("foreign", "proprietary") if name in chosen}
                frames, missing, index_bars = load_frames_for_run(symbols, kinds)
                reports = run_frames(conn, user_id, frames, index_bars, configs)
                if missing:
                    st.warning("Không có file nến: " + ", ".join(missing))
                sender = BrevoSender()
                for row in reports:
                    if row["created"] and row["signal_id"] is not None:
                        row["mail"] = maybe_notify(
                            conn,
                            user_id,
                            row["signal_id"],
                            row["symbol"],
                            row["filter_name"],
                            row["bar_date"],
                            row["signal_type"],
                            row["reason"],
                            row["price"],
                            sender,
                        )
                    else:
                        row["mail"] = ""
                if reports:
                    from datasource.kqkd import kqkd_map

                    board = pd.DataFrame(reports)[
                        ["symbol", "filter_name", "bar_date", "matched", "signal_type", "reason", "price", "mail"]
                    ]
                    board.columns = ["Mã", "Filter", "Ngày nến", "Khớp", "Tín hiệu", "Lý do", "Giá", "Mail"]
                    # KQKD chỉ cho các mã trong kết quả; tối đa 40 mã gọi cache/API.
                    filled = kqkd_map(board["Mã"].tolist(), cap=40)
                    board["KQKD quý hiện tại"] = [
                        filled.get(str(symbol).upper(), ("—", "—"))[0] for symbol in board["Mã"]
                    ]
                    board["KQKD quý cùng kỳ"] = [
                        filled.get(str(symbol).upper(), ("—", "—"))[1] for symbol in board["Mã"]
                    ]
                    st.caption("KQKD = LNST quý hiện tại / cùng kỳ. Thiếu dữ liệu thì «—».")
                    render_data_table(
                        board,
                        variant="analytical",
                        pin="Mã",
                        key_cols=["Tín hiệu", "Giá", "KQKD quý hiện tại"],
                        key="free_filter_board",
                    )
                    from ui.trading_desk import offer_to_desk

                    st.caption("Mỗi mã có thể đưa sang Trạm Trading. Mã đã có trong bảng vị thế thì không ghi đè.")
                    for index, item in board.iterrows():
                        label, action = st.columns([5, 2])
                        label.write(f"{item['Mã']} · {item['Filter']} · {item['Tín hiệu']}")
                        with action:
                            offer_to_desk(
                                str(item["Mã"]),
                                str(item["Filter"]),
                                f"to_desk_{index}_{item['Mã']}_{item['Filter']}",
                            )
                else:
                    st.info("Không có mã nào chạy được.")
                if any(row.get("mail") == "lỗi" for row in reports):
                    st.warning("Có thư gửi lỗi. Chi tiết nằm trong log. Các mã khác vẫn chạy.")

        upload = st.file_uploader("Nhập JSON", type="json")
        replace = st.checkbox("Ghi đè config hiện có khi nhập")
        if upload is not None and st.button("Nhập cấu hình"):
            try:
                imported = json.loads(upload.getvalue().decode("utf-8"))
                import_user(conn, user_id, imported, replace=replace)
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                st.error(str(exc))
            else:
                st.success("Đã nhập vào user hiện tại.")
                st.rerun()
    finally:
        conn.close()
