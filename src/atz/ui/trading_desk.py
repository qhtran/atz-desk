"""Bảng vị thế Trạm Trading. Lưu CSV local, giá lấy từ nến đã cache."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.technical import sma
from config import BARS_DIR, CAPITAL_TRANCHES, DATA_DIR
from engine.runner import load_symbol_csv
from ui.components import render_data_table
from ui.theme_tokens import css_buy_column, css_down, css_resist, css_signed_text, css_support, css_up

DESK_PATH = DATA_DIR / "trading_desk.csv"
_STORE_COLUMNS = (
    "Mã",
    "Giá mua",
    "Vùng hỗ trợ",
    "Vùng kháng cự",
    "Thăm dò 1/4 NAV",
    "Sai > cắt lỗ",
    "Đúng 1 tăng 1/4 NAV",
    "Đúng 2 tăng 1/2 NAV",
    "Đúng 3 full NAV",
    "Đúng 4 margin",
    "Lý do mua/bán",
    "Lý do cắt lỗ/chốt lãi",
)
_NUMBER_COLUMNS = (
    "Giá mua",
    "Vùng hỗ trợ",
    "Vùng kháng cự",
    "Thăm dò 1/4 NAV",
    "Đúng 1 tăng 1/4 NAV",
    "Đúng 2 tăng 1/2 NAV",
    "Đúng 3 full NAV",
    "Đúng 4 margin",
)
_VIEW_COLUMNS = (
    "Mã",
    "Xu hướng ngày",
    "Giá mua",
    "Vùng hỗ trợ",
    "Vùng kháng cự",
    "Giá hiện tại",
    "Thăm dò 1/4 NAV",
    "Sai > cắt lỗ",
    "Đúng 1 tăng 1/4 NAV",
    "Đúng 2 tăng 1/2 NAV",
    "Đúng 3 full NAV",
    "Đúng 4 margin",
    "Lãi/lỗ thương vụ",
)

def _empty_store() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_STORE_COLUMNS))


def load_desk() -> pd.DataFrame:
    if not DESK_PATH.exists():
        return _empty_store()
    try:
        frame = pd.read_csv(DESK_PATH)
    except Exception:
        return _empty_store()
    for column in _STORE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame["Mã"] = frame["Mã"].astype(str).str.upper()
    for column in _NUMBER_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["Sai > cắt lỗ"] = frame["Sai > cắt lỗ"].fillna("").astype(str)
    frame["Lý do mua/bán"] = frame["Lý do mua/bán"].fillna("").astype(str)
    frame["Lý do cắt lỗ/chốt lãi"] = frame["Lý do cắt lỗ/chốt lãi"].fillna("").astype(str)
    return frame[list(_STORE_COLUMNS)]


def save_desk(frame: pd.DataFrame) -> None:
    DESK_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame[list(_STORE_COLUMNS)].to_csv(DESK_PATH, index=False)


def _optional(value: object) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _bars(symbol: str) -> pd.DataFrame | None:
    try:
        frame = load_symbol_csv(BARS_DIR, symbol)
    except Exception:
        return None
    if frame is None or frame.empty or "close" not in frame.columns:
        return None
    return frame


def _last_close(frame: pd.DataFrame | None) -> float | None:
    if frame is None:
        return None
    close = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if close.empty:
        return None
    return float(close.iloc[-1])


def _trend(frame: pd.DataFrame | None, price: float | None) -> str:
    if frame is None or price is None:
        return "—"
    try:
        close = pd.to_numeric(frame["close"], errors="coerce")
        average = sma(close, 20)
        if pd.isna(average.iloc[-1]):
            return "—"
        line = float(average.iloc[-1])
    except Exception:
        return "—"
    if price > line:
        return "Tăng"
    if price < line:
        return "Giảm"
    return "Đi ngang"


def _zones(frame: pd.DataFrame | None) -> tuple[float | None, float | None]:
    if frame is None:
        return None, None
    try:
        low = pd.to_numeric(frame.get("low"), errors="coerce").dropna().tail(120)
        high = pd.to_numeric(frame.get("high"), errors="coerce").dropna().tail(120)
    except Exception:
        return None, None
    support = float(low.min()) if not low.empty else None
    resistance = float(high.max()) if not high.empty else None
    return support, resistance


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}"


def _price(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}"


def _pnl(price: float | None, buy: float | None) -> str:
    if price is None or buy is None or buy == 0:
        return "—"
    change = (price - buy) / buy * 100
    return f"{change:+.2f}%"


def suggestions(capital: float) -> dict[str, float]:
    """Mức vốn gợi ý từ NAV trên sidebar. Margin để trống vì chưa có hệ số."""
    quarter = capital / CAPITAL_TRANCHES if capital > 0 else 0.0
    return {
        "Thăm dò 1/4 NAV": quarter,
        "Đúng 1 tăng 1/4 NAV": quarter,
        "Đúng 2 tăng 1/2 NAV": capital / 2 if capital > 0 else 0.0,
        "Đúng 3 full NAV": capital,
    }


def view_board(store: pd.DataFrame, capital: float) -> pd.DataFrame:
    hinted = suggestions(capital)
    rows = []
    for _, item in store.iterrows():
        symbol = str(item["Mã"]).strip().upper()
        if not symbol or symbol == "NAN":
            continue
        frame = _bars(symbol)
        price = _last_close(frame)
        auto_support, auto_resistance = _zones(frame)
        buy = _optional(item["Giá mua"])
        support = _optional(item["Vùng hỗ trợ"])
        resistance = _optional(item["Vùng kháng cự"])
        stop = str(item["Sai > cắt lỗ"]).strip()
        if not stop and auto_support is not None:
            stop = _price(auto_support)
        row = {
            "Mã": symbol,
            "Xu hướng ngày": _trend(frame, price),
            "Giá mua": _price(buy),
            "Vùng hỗ trợ": _price(support if support is not None else auto_support),
            "Vùng kháng cự": _price(resistance if resistance is not None else auto_resistance),
            "Giá hiện tại": _price(price),
            "Sai > cắt lỗ": stop or "—",
            "Lãi/lỗ thương vụ": _pnl(price, buy),
        }
        for column, hint in (
            ("Thăm dò 1/4 NAV", hinted["Thăm dò 1/4 NAV"]),
            ("Đúng 1 tăng 1/4 NAV", hinted["Đúng 1 tăng 1/4 NAV"]),
            ("Đúng 2 tăng 1/2 NAV", hinted["Đúng 2 tăng 1/2 NAV"]),
            ("Đúng 3 full NAV", hinted["Đúng 3 full NAV"]),
            ("Đúng 4 margin", None),
        ):
            stored = _optional(item[column])
            row[column] = _money(stored if stored is not None else hint)
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=list(_VIEW_COLUMNS))
    return pd.DataFrame(rows)[list(_VIEW_COLUMNS)]


def upsert_position(store: pd.DataFrame, row: dict[str, object]) -> pd.DataFrame:
    symbol = str(row["Mã"]).strip().upper()
    row = dict(row)
    row["Mã"] = symbol
    kept = store.loc[store["Mã"].astype(str).str.upper() != symbol]
    return pd.concat([kept, pd.DataFrame([row])], ignore_index=True)


def delete_position(store: pd.DataFrame, symbol: str) -> pd.DataFrame:
    code = symbol.strip().upper()
    return store.loc[store["Mã"].astype(str).str.upper() != code].reset_index(drop=True)


def _known_symbols(store: pd.DataFrame) -> set[str]:
    if store.empty or "Mã" not in store.columns:
        return set()
    return {str(item).strip().upper() for item in store["Mã"] if str(item).strip()}


def adopt_from_signal(symbol: str, source: str) -> str:
    """Thêm mã từ bộ lọc. Mã đã có thì trả 'exists' và không ghi đè."""
    code = symbol.strip().upper()
    if not code:
        return "invalid"
    store = load_desk()
    if code in _known_symbols(store):
        return "exists"
    row = {column: pd.NA for column in _STORE_COLUMNS}
    row["Mã"] = code
    row["Sai > cắt lỗ"] = ""
    row["Lý do mua/bán"] = f"Từ tín hiệu lọc - {source}".strip()
    row["Lý do cắt lỗ/chốt lãi"] = ""
    save_desk(upsert_position(store, row))
    return "added"


def offer_to_desk(symbol: str, source: str, key: str) -> None:
    """Nút đưa một mã sang Trạm Trading. Giá và xu hướng hiện khi mở bảng vị thế."""
    if not st.button("Đưa vào Trạm Trading", key=key):
        return
    status = adopt_from_signal(symbol, source)
    if status == "added":
        st.success(f"Đã đưa {symbol} vào Trạm Trading.")
    elif status == "exists":
        st.info(f"{symbol} đã có trong Trạm Trading. Không ghi đè.")
    else:
        st.warning("Thiếu mã để đưa sang Trạm Trading.")


def _blank_number(value: float | None) -> float:
    return 0.0 if value is None or pd.isna(value) else float(value)


def _parse_display_number(value: object) -> float | None:
    """Đọc số từ ô đã format (vd. '11.80', '+1.27%', '25,000,000')."""
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {"—", "-", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def style_desk_board(board: pd.DataFrame):
    """Tô màu theo checklist F1 mục 6 (mentor)."""
    if board.empty:
        return board

    buy_nums = [_parse_display_number(v) for v in board["Giá mua"]]
    cur_nums = [_parse_display_number(v) for v in board["Giá hiện tại"]]

    def paint_current(_: object) -> list[str]:
        styles: list[str] = []
        for buy, cur in zip(buy_nums, cur_nums, strict=True):
            if buy is None or cur is None:
                styles.append("")
            elif cur > buy:
                styles.append(css_up())
            elif cur < buy:
                styles.append(css_down())
            else:
                styles.append("")
        return styles

    styled = board.style.map(css_signed_text, subset=["Lãi/lỗ thương vụ"])
    styled = styled.map(css_signed_text, subset=["Xu hướng ngày"])
    styled = styled.map(lambda _: css_buy_column(), subset=["Giá mua"])
    styled = styled.map(lambda _: css_support(), subset=["Vùng hỗ trợ"])
    styled = styled.map(lambda _: css_resist(), subset=["Vùng kháng cự"])
    styled = styled.apply(paint_current, subset=["Giá hiện tại"], axis=0)
    return styled


def show_trading_desk(capital: float) -> None:
    st.subheader("Quản trị vị thế")
    st.caption(
        "Giá hiện tại, xu hướng ngày (MA20), hỗ trợ và kháng cự lấy từ nến đã lưu khi có. "
        "Mức 1/4, 1/2 và full NAV là gợi ý theo vốn trên sidebar nếu ô đó để trống. "
        "Margin chưa có hệ số, để «—» cho đến khi tự điền. Lãi/lỗ là % so với giá mua. "
        "Màu: lãi/tăng/giá trên giá mua = xanh; lỗ/giảm/giá dưới giá mua = đỏ; "
        "giá mua = vàng; hỗ trợ = đỏ; kháng cự = xanh."
    )
    store = load_desk()
    board = view_board(store, capital)
    render_data_table(
        style_desk_board(board),
        pin="Mã",
        key_cols=["Xu hướng ngày", "Giá mua", "Giá hiện tại", "Lãi/lỗ thương vụ"],
        key="desk_board",
        alt="Bảng quản trị vị thế Trạm Trading, đã tô màu lãi lỗ và xu hướng",
    )
    if not store.empty:
        for _, item in store.iterrows():
            symbol = str(item["Mã"]).strip().upper()
            buy_reason = str(item["Lý do mua/bán"]).strip()
            exit_reason = str(item["Lý do cắt lỗ/chốt lãi"]).strip()
            with st.expander(f"Ghi chú {symbol}", expanded=False):
                st.markdown("**Lý do mua/bán**")
                st.write(buy_reason or "—")
                st.markdown("**Lý do cắt lỗ/chốt lãi**")
                st.write(exit_reason or "—")

    st.markdown("**Thêm hoặc sửa mã**")
    choices = [""] + store["Mã"].astype(str).str.upper().tolist()
    selected = st.selectbox("Mã đã có, để trống nếu thêm mới", choices, key="desk_edit_symbol")
    current = store.loc[store["Mã"].astype(str).str.upper() == selected]
    current_row = current.iloc[0] if not current.empty else None
    with st.form("trading_desk_form"):
        left, right = st.columns(2)
        symbol = left.text_input(
            "Mã",
            value="" if current_row is None else str(current_row["Mã"]),
            key=f"desk_symbol_{selected}",
        )
        buy_price = right.number_input(
            "Giá mua",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Giá mua"]),
            step=0.05,
            key=f"desk_buy_{selected}",
        )
        support = left.number_input(
            "Vùng hỗ trợ (0 = lấy từ nến)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Vùng hỗ trợ"]),
            step=0.05,
            key=f"desk_support_{selected}",
        )
        resistance = right.number_input(
            "Vùng kháng cự (0 = lấy từ nến)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Vùng kháng cự"]),
            step=0.05,
            key=f"desk_resistance_{selected}",
        )
        probe = left.number_input(
            "Thăm dò 1/4 NAV (0 = gợi ý)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Thăm dò 1/4 NAV"]),
            step=1_000_000.0,
            key=f"desk_probe_{selected}",
        )
        stop = right.text_input(
            "Sai > cắt lỗ",
            value="" if current_row is None else str(current_row["Sai > cắt lỗ"]),
            key=f"desk_stop_{selected}",
        )
        add_quarter = left.number_input(
            "Đúng 1 tăng 1/4 NAV (0 = gợi ý)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Đúng 1 tăng 1/4 NAV"]),
            step=1_000_000.0,
            key=f"desk_q1_{selected}",
        )
        add_half = right.number_input(
            "Đúng 2 tăng 1/2 NAV (0 = gợi ý)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Đúng 2 tăng 1/2 NAV"]),
            step=1_000_000.0,
            key=f"desk_half_{selected}",
        )
        full_nav = left.number_input(
            "Đúng 3 full NAV (0 = gợi ý)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Đúng 3 full NAV"]),
            step=1_000_000.0,
            key=f"desk_full_{selected}",
        )
        margin = right.number_input(
            "Đúng 4 margin (0 = để trống)",
            min_value=0.0,
            value=_blank_number(None if current_row is None else current_row["Đúng 4 margin"]),
            step=1_000_000.0,
            key=f"desk_margin_{selected}",
        )
        reason_trade = st.text_area(
            "Lý do mua/bán",
            value="" if current_row is None else str(current_row["Lý do mua/bán"]),
            key=f"desk_reason_{selected}",
        )
        reason_exit = st.text_area(
            "Lý do cắt lỗ/chốt lãi",
            value="" if current_row is None else str(current_row["Lý do cắt lỗ/chốt lãi"]),
            key=f"desk_exit_{selected}",
        )
        save_clicked = st.form_submit_button("Lưu mã")
    if save_clicked:
        code = symbol.strip().upper()
        if not code:
            st.warning("Cần nhập mã.")
        else:
            saved = upsert_position(
                store,
                {
                    "Mã": code,
                    "Giá mua": buy_price or pd.NA,
                    "Vùng hỗ trợ": support or pd.NA,
                    "Vùng kháng cự": resistance or pd.NA,
                    "Thăm dò 1/4 NAV": probe or pd.NA,
                    "Sai > cắt lỗ": stop.strip(),
                    "Đúng 1 tăng 1/4 NAV": add_quarter or pd.NA,
                    "Đúng 2 tăng 1/2 NAV": add_half or pd.NA,
                    "Đúng 3 full NAV": full_nav or pd.NA,
                    "Đúng 4 margin": margin or pd.NA,
                    "Lý do mua/bán": reason_trade.strip(),
                    "Lý do cắt lỗ/chốt lãi": reason_exit.strip(),
                },
            )
            save_desk(saved)
            st.success(f"Đã lưu {code}.")
            st.rerun()

    if selected:
        if st.button(f"Xóa {selected}", key="desk_delete"):
            save_desk(delete_position(store, selected))
            st.success(f"Đã xóa {selected}.")
            st.rerun()
