"""Trang Realtime (Module 5): bảng giá, vị thế live, thông báo trong app, cài đặt, health (admin).

Chỉ phần bảng chạy lại theo st.fragment(run_every=...) (3s trong giờ giao dịch, 30s ngoài giờ),
không chạy lại cả trang. Dữ liệu đọc qua ui_realtime.data (cache trong process, MGET).
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime

import pandas as pd
import streamlit as st

from engine.identity import current_username
from ui.components import render_data_table
from ui.theme_tokens import css_signed_number
from ui_realtime import data
from ui_realtime import index_cards
from order_helper import core as oah
from ui_realtime.log import ERR_SYS_SQLITE, ERR_UI_FALLBACK, TZ, log

BOT_URL = "https://t.me/atz_alert_bot"


def _cfg() -> dict:
    return data.reader().cfg   # singleton theo process, đọc yaml 1 lần


def _db():
    return data.open_db(_cfg())


def _whoami() -> tuple[str, int]:
    username = current_username()
    if st.session_state.get("rt_user") != username:
        conn = _db()
        try:
            st.session_state["rt_uid"] = data.user_id_for(conn, username)
        finally:
            conn.close()
        st.session_state["rt_user"] = username
    return username, int(st.session_state["rt_uid"])


def _tick(name: str, user_id: int, interval) -> None:
    """Đếm rerun fragment; log FRAGMENT mỗi N lần để có bằng chứng mà không spam."""
    key = f"rt_n_{name}"
    st.session_state[key] = st.session_state.get(key, 0) + 1
    n = st.session_state[key]
    every = int(_cfg()["ui_realtime"]["fragment_log_every"])
    if n == 1 or n % every == 0:
        r = data.reader()
        log("FRAGMENT", f"{name} rerun #{n} interval={interval}s", user_id=user_id, fragment=name, reruns=n,
            redis_calls=r.stats["redis_calls"], cache_hits=r.stats["cache_hits"])


def _stamp(interval) -> str:
    now = datetime.now(TZ).strftime("%H:%M:%S")
    mode = f"tự cập nhật mỗi {interval:g}s" if interval else "ngoài giờ, không tự cập nhật"
    return f"Cập nhật lúc {now} · {mode}"


# ------------------------------------------------------------------ bảng giá
def _fallback_board(reason: str, user_id: int) -> None:
    st.warning(f"Đang dùng dữ liệu dự phòng (giá từ lần quét gần nhất, không realtime): {reason}")
    if not st.session_state.get("rt_fb_logged"):
        st.session_state["rt_fb_logged"] = True
        log("BOARD", f"fallback to top20 cache: {reason}", error_code=ERR_UI_FALLBACK, user_id=user_id)
    try:
        from datasource.cache import read_cache
        board = read_cache()
    except Exception as error:  # noqa: BLE001
        st.error(f"Không đọc được dữ liệu dự phòng: {error}")
        return
    cols = [c for c in ("Mã", "Giá", "RS 3 tháng (%)", "ROE (%)", "KLGD TB 20 phiên") if c in board.columns]
    render_data_table(board[cols] if cols else board, key="rt_board_fb")


def _index_cards(user_id: int) -> None:
    """Thẻ chỉ số kiểu FireAnt (VNINDEX, HNX, UPCOM, VN30, VN30F1M/F2M) ở đầu bảng giá, cùng fragment."""
    try:
        st.markdown(index_cards.render_html(data.reader(), float(_cfg()["ui_realtime"]["quote_stale_seconds"]), user_id),
                    unsafe_allow_html=True)
    except Exception as e:  # noqa: BLE001 - thẻ chỉ số lỗi không được làm hỏng bảng giá
        log("INDEX", f"render failed: {type(e).__name__}: {e}", error_code=index_cards.ERR_UI_INDEX, user_id=user_id)


def _board_controls(user_id: int, username: str) -> tuple[str, str]:
    """Search + chọn mã + ghim (ngoài fragment — gõ không bị reset mỗi chu kỳ)."""
    from datasource.user_trading import load_pinned_symbols, toggle_pinned_symbol
    from ui.debug_overlay import dbg_anchor

    dbg_anchor("DBG-RT-PIN")
    cols = st.columns([2, 2, 1])
    query = cols[0].text_input(
        "Tìm mã nhanh",
        key="rt_symbol_filter",
        placeholder="Gõ VIC, FPT… (lọc bảng bên dưới)",
        help="Thay keyboard jump kiểu Fireant trên Streamlit.",
    )
    quotes: list = []
    symbols: list[str] = []
    try:
        raw = data.reader().quotes()
        quotes = raw if isinstance(raw, list) else []
        symbols = sorted(
            {str(q.get("symbol") or "").upper() for q in quotes if q.get("symbol")}
        )
    except Exception:  # noqa: BLE001
        quotes, symbols = [], []
    options = ["—"] + symbols
    current = st.session_state.get("rt_detail_pick") or "—"
    if current not in options:
        current = "—"
    picked = cols[1].selectbox(
        "Chi tiết mã (Time & Sales / cảnh báo)",
        options,
        index=options.index(current),
        key="rt_detail_pick",
    )
    symbol = "" if picked in (None, "—") else str(picked).upper()
    pins = load_pinned_symbols(username)
    st.session_state["rt_pins"] = pins
    with cols[2]:
        st.write("")  # căn nút
        if symbol:
            pinned_now = symbol in pins
            label = f"Bỏ ghim {symbol}" if pinned_now else f"Ghim {symbol}"
            if st.button(label, width="stretch", key="rt_pin_toggle"):
                pins = toggle_pinned_symbol(username, symbol)
                st.session_state["rt_pins"] = pins
                st.rerun()
        else:
            st.caption("Chọn mã để ghim")
    if pins:
        st.caption("Ghim (đầu bảng): " + " · ".join(pins))
    _time_sales_panel(user_id, symbol, quotes)
    return str(query or ""), symbol


def _time_sales_panel(user_id: int, symbol: str, quotes: list) -> None:
    """MVP: panel theo click/select — chưa có feed khớp lệnh."""
    from ui_realtime.board_view import pick_quote_row

    label = f"Khớp lệnh / cảnh báo — {symbol}" if symbol else "Khớp lệnh / cảnh báo"
    with st.expander(label, expanded=bool(symbol)):
        if not symbol:
            st.caption("Chọn mã ở ô bên phải để xem nhanh. Hover từng dòng chưa hỗ trợ trên Streamlit dataframe.")
            return
        rows = data.quote_rows(quotes, float(_cfg()["ui_realtime"]["quote_stale_seconds"])) if quotes else []
        row = pick_quote_row(rows, symbol)
        if row:
            c = st.columns(4)
            c[0].metric("Giá", f"{row.get('Giá') or 0:,.0f}")
            c[1].metric("+/-", f"{row.get('+/-') or 0:+,.0f}")
            c[2].metric("%", f"{row.get('%') or 0:+.2f}")
            c[3].metric("TC", f"{row.get('TC') or 0:,.0f}")
        st.info(
            "Time & Sales realtime chưa nối feed. Dùng bảng điện tử HSX làm tham chiếu; "
            "cảnh báo giá cá nhân sẽ gắn sau (alert dispatcher)."
        )
        st.link_button("Mở rtboard.hsx.vn", "https://rtboard.hsx.vn/", width="stretch")
        if st.button("Nhắc tạo cảnh báo giá (stub)", key=f"rt_alert_stub_{symbol}"):
            log("BOARD", f"alert stub clicked symbol={symbol}", user_id=user_id)
            st.success(f"Đã ghi nhận yêu cầu cảnh báo cho {symbol} (chưa lưu rule).")


def _board(user_id: int, interval, query: str = "") -> None:
    from ui.debug_overlay import dbg_anchor

    dbg_anchor("DBG-RT-BOARD")
    _tick("board", user_id, interval)
    _index_cards(user_id)
    r = data.reader()
    quotes = r.quotes()
    if quotes is None:
        _fallback_board(f"Redis không phản hồi ({r.last_error or 'đang thử lại'})", user_id)
        st.caption(_stamp(interval))
        return
    if not quotes:
        _fallback_board("Redis chưa có quote nào", user_id)
        return
    st.session_state["rt_fb_logged"] = False
    rows = data.quote_rows(quotes, float(_cfg()["ui_realtime"]["quote_stale_seconds"]))
    stale = sum(1 for x in rows if x["_stale"])
    newest = max((x["_ts"] for x in rows if x["_ts"]), default=None)
    from ui.price_action import price_state
    from ui.sparkline import spark_image_uri, trend_image_column
    from ui.stock_item import realtime_board_frame
    from ui.theme_tokens import FIREANT_CSS, css_flash, css_for_price_state
    from ui_realtime import board_view as bv

    st.markdown(FIREANT_CSS, unsafe_allow_html=True)
    frame = realtime_board_frame(rows)
    frame = frame.copy()
    # Lọc theo ô tìm (session) — ưu tiên tham số, fallback key
    needle = query or str(st.session_state.get("rt_symbol_filter") or "")
    frame = bv.filter_by_symbol(frame, needle)
    pins = list(st.session_state.get("rt_pins") or [])
    if not pins:
        try:
            from datasource.user_trading import load_pinned_symbols
            from engine.identity import current_username as _uname

            pins = load_pinned_symbols(_uname())
            st.session_state["rt_pins"] = pins
        except Exception:  # noqa: BLE001
            pins = []
    frame = bv.sort_pinned_first(frame, pins)

    state_by: dict[str, str] = {}
    for _, row in frame.iterrows():
        code = str(row.get("Mã") or "")
        if not code:
            continue
        state_by[code] = price_state(
            row.get("Giá"),
            row.get("TC"),
            exchange=str(row.get("Sàn") or ""),
            ceiling=row.get("Trần"),
            floor=row.get("Sàn giá"),
        )

    prev_prices: dict = st.session_state.get("rt_prev_prices") or {}
    next_prices: dict[str, float] = {}
    for _, row in frame.iterrows():
        code = str(row.get("Mã") or "")
        try:
            price = float(row["Giá"]) if row.get("Giá") is not None else None
        except (TypeError, ValueError):
            price = None
        if code and price is not None:
            next_prices[code] = price
    rt_cfg = _cfg()["ui_realtime"]
    min_tick = float(rt_cfg.get("flash_min_tick_vnd", 50))
    hold_cycles = int(rt_cfg.get("flash_hold_cycles", 2))
    fresh = bv.detect_price_flashes(prev_prices, next_prices, min_tick=min_tick)
    hold = st.session_state.get("rt_flash_hold") or {}
    flashed, hold = bv.merge_flash_hold(fresh, hold, hold_cycles=hold_cycles)
    st.session_state["rt_flash_hold"] = hold
    st.session_state["rt_prev_prices"] = next_prices

    spark_cache: dict = st.session_state.setdefault("rt_spark_uri", {})
    uris = []
    for spark, pct, code, price in zip(
        frame["Xu hướng"], frame["%"], frame["Mã"], frame["Giá"]
    ):
        code_s = str(code or "x")
        state = state_by.get(code_s)
        try:
            px = float(price) if price is not None else None
        except (TypeError, ValueError):
            px = None
        series = list(spark) if isinstance(spark, list) else []
        uris.append(
            bv.cached_spark_uri(
                spark_cache,
                code=code_s,
                spark=series,
                change=pct,
                state=state,
                price=px,
                builder=lambda s=series, p=pct, c=code_s, stt=state: spark_image_uri(
                    s, p, c, state=stt
                ),
            )
        )
    frame["Xu hướng"] = uris
    if stale:
        st.warning(f"⚠️ {stale}/{len(rows)} mã có giá cũ (> {_cfg()['ui_realtime']['quote_stale_seconds']}s hoặc nguồn gắn cờ stale).")
    if needle.strip() and frame.empty:
        st.info(f"Không có mã khớp «{needle.strip()}».")
        return

    paint = {"Giá", "+/-", "%", "Mã"}

    def _rt_row_colors(row: pd.Series) -> list[str]:
        code = str(row.get("Mã") or "")
        tone = css_for_price_state(state_by.get(code, ""))
        flash = f"; {css_flash(flashed[code], strong=True)}" if code in flashed else ""
        styles = []
        for name in row.index:
            if name in paint and (tone or flash):
                # Mã: chỉ nền flash, giữ chữ mặc định; Giá/+/-/%: màu state + flash
                if name == "Mã":
                    styles.append(flash.lstrip("; ").strip() if flash else "")
                else:
                    styles.append((tone + flash).strip("; ") if (tone or flash) else "")
            else:
                styles.append("")
        return styles

    styled = frame.style.format(
        {
            "Giá": "{:,.0f}",
            "+/-": "{:+,.0f}",
            "%": "{:+.2f}",
            "Mở": "{:,.0f}",
            "Cao": "{:,.0f}",
            "Thấp": "{:,.0f}",
            "TC": "{:,.0f}",
        },
        subset=[c for c in frame.columns if c not in ("Xu hướng", "Sàn", "Trần", "Sàn giá")],
        na_rep="-",
    ).apply(_rt_row_colors, axis=1)
    hide_cols = [c for c in ("Sàn", "Trần", "Sàn giá") if c in frame.columns]
    if hide_cols:
        styled = styled.hide(axis="columns", subset=hide_cols)
    render_data_table(
        styled,
        key_cols=["Giá", "%", "Xu hướng", "Trạng thái"],
        key="rt_board",
        column_config={"Xu hướng": trend_image_column("Xu hướng", width="small")},
        alt="Bảng giá realtime kèm sparkline, trần/sàn và flash khi giá đổi",
    )
    tick = newest.astimezone(TZ).strftime("%H:%M:%S") if newest else "?"
    n_ceil = sum(1 for s in state_by.values() if s == "ceiling")
    n_floor = sum(1 for s in state_by.values() if s == "floor")
    n_api = sum(1 for _, row in frame.iterrows() if row.get("Trần") is not None and row.get("Sàn giá") is not None)
    st.caption(
        f"{_stamp(interval)} · quote mới nhất {tick} · hiện {len(frame)}/{len(rows)} mã · "
        f"trần {n_ceil} · sàn {n_floor} · limit API {n_api}/{len(frame)} · spark cache {len(spark_cache)} · "
        "tím=trần · xanh dương=sàn · xanh/đỏ/vàng=Δ"
    )


# ------------------------------------------------------------------ vị thế
def _positions_live(user_id: int, interval) -> None:
    _tick("positions", user_id, interval)
    conn = _db()
    try:
        mine = data.list_positions(conn, user_id)
    finally:
        conn.close()
    if not mine:
        st.info("Chưa có vị thế mở. Thêm ở form bên dưới.")
        return
    live = data.reader().live_positions(user_id)
    if live is None:
        st.warning("Không đọc được P&L realtime (Redis). Hiện vị thế đã lưu, chưa có lãi/lỗ.")
        live = {}
    rows = []
    for p in mine:
        s = live.get(int(p["id"]), {})
        rows.append({"ID": p["id"], "Mã": p["symbol"], "KL": p["quantity"], "Giá vốn": p["entry_price"],
                     "Giá": s.get("price"), "Lãi/lỗ": s.get("pnl"), "%": s.get("pnl_pct"),
                     "Cắt lỗ": p["stop_loss"], "Chốt lời": p["take_profit"],
                     "Cảnh báo": " ".join(x for x, c in (("SL✓", p["sl_hit_at"]), ("TP✓", p["tp_hit_at"])) if c) or "-",
                     "Trạng thái": "⚠️ cũ" if s.get("stale") else ("live" if s else "chờ giá"),
                     "Lúc": str(s.get("quote_ts") or "")[11:19] or "-"})
    frame = pd.DataFrame(rows)
    total = pd.to_numeric(frame["Lãi/lỗ"], errors="coerce").sum()
    st.metric("Tổng lãi/lỗ (VND)", f"{total:+,.0f}")
    styled = frame.style.format({"KL": "{:,.0f}", "Giá vốn": "{:,.0f}", "Giá": "{:,.0f}", "Lãi/lỗ": "{:+,.0f}", "%": "{:+.2f}",
                                 "Cắt lỗ": "{:,.0f}", "Chốt lời": "{:,.0f}"}, na_rep="-").map(
        css_signed_number, subset=["Lãi/lỗ", "%"])
    render_data_table(styled, key_cols=["Giá", "Lãi/lỗ", "%"], key="rt_pos")
    st.caption(f"{_stamp(interval)} · Lãi/lỗ cập nhật khi có giá mới, chậm nhất khoảng 15 giây.")


def _position_forms(user_id: int) -> None:
    unit_label = st.radio("Đơn vị giá nhập", ["VND", "Nghìn đồng"], horizontal=True, key="rt_unit")
    unit = "k" if unit_label == "Nghìn đồng" else "vnd"
    with st.form("rt_add_pos", clear_on_submit=True):
        st.markdown("**Thêm vị thế (mua)**")
        c = st.columns(2)
        symbol = c[0].text_input("Mã", max_chars=10)
        qty = c[1].number_input("Khối lượng", min_value=0, step=100, value=0)
        c = st.columns(3)
        entry = c[0].number_input("Giá vốn", min_value=0.0, value=0.0, step=100.0 if unit == "vnd" else 0.1)
        sl = c[1].number_input("Cắt lỗ (0 = không)", min_value=0.0, value=0.0, step=100.0 if unit == "vnd" else 0.1)
        tp = c[2].number_input("Chốt lời (0 = không)", min_value=0.0, value=0.0, step=100.0 if unit == "vnd" else 0.1)
        note = st.text_input("Ghi chú", max_chars=200)
        if st.form_submit_button("Thêm vị thế"):
            _do(lambda conn: data.add_position(conn, user_id, symbol, qty, entry, sl, tp, note, unit), "Đã thêm vị thế.")
    conn = _db()
    try:
        mine = data.list_positions(conn, user_id)
    finally:
        conn.close()
    if not mine:
        return
    labels = {f"#{p['id']} {p['symbol']} {p['quantity']:,.0f} @ {p['entry_price']:,.0f}": p["id"] for p in mine}
    with st.form("rt_edit_pos"):
        st.markdown("**Sửa cắt lỗ / chốt lời hoặc đóng vị thế**")
        choice = st.selectbox("Vị thế", list(labels))
        c = st.columns(2)
        sl = c[0].number_input("Cắt lỗ mới (0 = giữ)", min_value=0.0, value=0.0, step=100.0 if unit == "vnd" else 0.1)
        tp = c[1].number_input("Chốt lời mới (0 = giữ)", min_value=0.0, value=0.0, step=100.0 if unit == "vnd" else 0.1)
        c = st.columns(2)
        save = c[0].form_submit_button("Lưu mức mới")
        close = c[1].form_submit_button("Đóng vị thế")
    if save:
        _do(lambda conn: data.update_levels(conn, user_id, labels[choice], sl, tp, unit), "Đã lưu. Cảnh báo mức đó được bật lại.")
    elif close:
        _do(lambda conn: data.close_position(conn, user_id, labels[choice]), "Đã đóng vị thế.")


def _do(action, ok_msg: str) -> None:
    conn = _db()
    try:
        action(conn)
    except data.UserError as e:
        st.error(f"{e} ({e.code})")
        return
    except Exception as e:  # noqa: BLE001
        log("ACTION", f"unexpected: {e}", error_code=ERR_SYS_SQLITE)
        st.error(f"Lỗi hệ thống ({ERR_SYS_SQLITE}): {e}")
        return
    finally:
        conn.close()
    st.toast(ok_msg)
    st.rerun()


# ------------------------------------------------------------------ thông báo trong app
def _unread(user_id: int, items: list[dict]) -> int:
    seen = data.reader().seen(user_id)
    return sum(1 for x in items if str(x.get("timestamp", "")) > seen)


def _alerts(user_id: int, interval) -> None:
    _tick("alerts", user_id, interval)
    items = data.reader().inapp(user_id)
    if items is None:
        st.warning("Không đọc được thông báo (Redis đang lỗi).")
        return
    unread = _unread(user_id, items)
    c = st.columns([3, 1])
    c[0].markdown(f"**{unread} chưa đọc** / {len(items)} gần nhất")
    if items and c[1].button("Đánh dấu đã đọc", key="rt_seen"):
        data.reader().mark_seen(user_id, max(str(x.get("timestamp", "")) for x in items))
        log("ALERTS-READ", f"marked {unread} read", user_id=user_id)
        st.rerun(scope="fragment")
    if not items:
        st.info("Chưa có thông báo.")
        return
    seen = data.reader().seen(user_id)
    frame = pd.DataFrame([{"": "🔵" if str(x.get("timestamp", "")) > seen else "", "Lúc": str(x.get("timestamp", ""))[11:19],
                           "Ngày": str(x.get("timestamp", ""))[:10], "Mã": x.get("symbol"),
                           "Chiều": {"BUY": "Mua", "SELL": "Bán"}.get(x.get("direction"), x.get("direction")),
                           "Giá": x.get("price"), "Bộ lọc": x.get("filter_name"), "Lý do": x.get("reason")} for x in items])
    render_data_table(frame.style.format({"Giá": "{:,.0f}"}, na_rep="-"), pin=("Mã",), key="rt_alerts")
    st.caption(_stamp(interval))


# ------------------------------------------------------------------ cài đặt
def _settings(user_id: int) -> None:
    conn = _db()
    try:
        cur = data.get_settings(conn, user_id)
    finally:
        conn.close()
    st.markdown(f"Để nhận Telegram riêng: mở [{BOT_URL.removeprefix('https://')}]({BOT_URL}), bấm **Start** và gửi `hi`. "
                "Lấy chat_id của bạn (số) từ admin hoặc @userinfobot rồi dán vào ô dưới.")
    qh = cur["quiet_hours"] or {}
    with st.form("rt_settings"):
        chat = st.text_input("Telegram chat_id", value=str(cur["telegram_chat_id"]))
        tg_on = st.toggle("Nhận Telegram", value=cur["telegram_bat"])
        email = st.text_input("Email nhận thông báo", value=cur["email"])
        em_on = st.toggle("Nhận email (dự phòng khi Telegram lỗi)", value=cur["email_bat"])
        c = st.columns(2)
        qs = c[0].text_input("Giờ yên lặng từ (HH:MM, trống = tắt)", value=qh.get("start", ""))
        qe = c[1].text_input("đến (HH:MM)", value=qh.get("end", ""))
        st.caption("Trong giờ yên lặng chỉ lưu thông báo trong app, không gửi Telegram/email.")
        if st.form_submit_button("Lưu cài đặt"):
            _do(lambda conn: data.save_settings(conn, user_id, chat, tg_on, email, em_on, qs, qe), "Đã lưu cài đặt.")


# ------------------------------------------------------------------ health (admin)
def _health(user_id: int, interval) -> None:
    _tick("health", user_id, interval)
    h = data.reader().health()
    rows = [{"Thành phần": k, "Trạng thái": "✅" if v["ok"] else "❌", "Chi tiết": v["detail"]} for k, v in h.items()]
    render_data_table(pd.DataFrame(rows), pin=("Thành phần",), key="rt_health")
    st.caption(_stamp(interval))


# ------------------------------------------------------------------ trang

# ------------------------------------------------------------------ Module 6: Order Action Helper
def _signals(user_id: int) -> None:
    """Lịch sử tín hiệu của chính user + chuỗi copy (st.code có nút copy). Không đặt lệnh."""
    c = st.columns([1, 1, 1, 1])
    days = c[0].number_input("Số ngày", 1, oah.MAX_DAYS, 7, key="oah_days")
    symbol = c[1].text_input("Mã (trống = tất cả)", key="oah_sym")
    side = c[2].selectbox("Chiều", ["Tất cả", "MUA", "BÁN"], key="oah_side")
    limit = c[3].number_input("Số dòng", 1, oah.MAX_LIMIT, 50, key="oah_limit")
    try:
        with closing(_db()) as conn:
            items = oah.history(conn, user_id, days=days, limit=limit, symbol=symbol,
                                side=None if side == "Tất cả" else side)
    except oah.FilterError as e:
        st.error(f"{e} ({e.code})")
        return
    except Exception as e:  # noqa: BLE001
        log("OAH-HISTORY", f"sqlite failed: {e}", error_code=ERR_SYS_SQLITE, user_id=user_id)
        st.error("Không đọc được lịch sử tín hiệu (ERR-SYS-002).")
        return
    if not items:
        st.info("Chưa có tín hiệu trong khoảng này.")
        return
    st.caption(
        "Bấm biểu tượng copy trên khung để chép chuỗi chuẩn "
        "(MÃ | HÀNH ĐỘNG | KL | GIÁ nghìn đồng | SL | TP). Chỉ hỗ trợ — tự đặt lệnh trên app sàn."
    )
    for s in items[:10]:
        label = s["copy"] + ("  🔒 riêng" if s["private"] else "")
        st.code(label, language=None)
        with st.expander(f"Chi tiết {s['symbol']} · {s['time_text']}", expanded=False):
            st.text(s["text"])
    frame = pd.DataFrame(
        [
            {
                "Lúc": s["time_text"],
                "Mã": s["symbol"],
                "Chiều": s["direction"],
                "Giá": s["price"],
                "Bộ lọc": s["filter_name"],
                "Lý do": s["reason"],
                "Copy": s["copy"],
            }
            for s in items
        ]
    )
    render_data_table(frame.style.format({"Giá": "{:,.0f}"}, na_rep="-"), pin=("Mã",), key="oah_table")
    st.download_button("Tải CSV", oah.to_csv(items), file_name="tin_hieu.csv", mime="text/csv", key="oah_csv")


def show_realtime() -> None:
    from ui.debug_overlay import dbg_anchor

    dbg_anchor("DBG-REALTIME")
    try:
        cfg = _cfg()
    except Exception as e:  # noqa: BLE001
        log("PAGE", f"config load failed: {e}", error_code="ERR-SYS-003")
        st.error(f"Không đọc được config/ui_realtime.yaml (ERR-SYS-003): {e}")
        return
    username, user_id = _whoami()
    interval = data.refresh_seconds(cfg)
    if not st.session_state.get("rt_page_logged"):
        st.session_state["rt_page_logged"] = True
        log("PAGE", f"open realtime page interval={interval}", user_id=user_id, username=username)
    items = data.reader().inapp(user_id) or []
    unread = _unread(user_id, items) if items else 0
    sections = ["Bảng giá", "Vị thế", f"Thông báo ({unread})" if unread else "Thông báo", "Tín hiệu", "Cài đặt"]
    if username in cfg["ui_realtime"]["admin_users"]:
        sections.append("Health")
    dbg_anchor("DBG-RT-SECTION")
    section = st.segmented_control("Realtime", sections, default="Bảng giá", key="rt_section")
    section = (section or "Bảng giá").split(" (")[0]
    status = "Trong giờ giao dịch" if data.in_trading(cfg) else "Ngoài giờ giao dịch"
    st.caption(f"{status} · user {username}")
    if section == "Bảng giá":
        query, _detail = _board_controls(user_id, username)
        st.fragment(run_every=interval)(_board)(user_id, interval, query)
    elif section == "Vị thế":
        st.fragment(run_every=interval)(_positions_live)(user_id, interval)
        _position_forms(user_id)
    elif section == "Thông báo":
        st.fragment(run_every=interval)(_alerts)(user_id, interval)
    elif section == "Tín hiệu":
        _signals(user_id)
    elif section == "Cài đặt":
        _settings(user_id)
    elif section == "Health" and username in cfg["ui_realtime"]["admin_users"]:
        st.fragment(run_every=interval)(_health)(user_id, interval)
