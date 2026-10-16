"""Tab Cảnh báo và bản tin. Kiểm tra khi mở tab, không chạy nền."""

from __future__ import annotations

import streamlit as st

from datasource.alerts import ALERT_KINDS, PRICE_KINDS, add_alert, check_alerts, delete_alert, list_alerts, read_bulletin


def bulletin_excerpt(text: str, max_lines: int = 6, max_chars: int = 700) -> str:
    """Đoạn đầu bản tin: tiêu đề + vài dòng đầu, dừng trước bảng hoặc mục thứ hai."""
    lines = text.strip().splitlines()
    picked: list[str] = []
    sections = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            break
        if stripped.startswith("## "):
            sections += 1
            if sections > 1:
                break
        picked.append(line)
        if sum(1 for item in picked if item.strip()) >= max_lines or len("\n".join(picked)) >= max_chars:
            break
    excerpt = "\n".join(picked).strip()
    return text.strip() if len(excerpt) >= 0.85 * len(text.strip()) else excerpt


def show_alerts() -> None:
    st.subheader("Bản tin")
    bulletin = read_bulletin()
    if bulletin is None:
        st.info("Chưa có bản tin hôm nay.")
    else:
        excerpt = bulletin_excerpt(bulletin)
        if excerpt == bulletin:
            st.markdown(bulletin)
        else:
            st.markdown(excerpt)
            with st.expander("Xem toàn bộ bản tin", expanded=False):
                st.markdown(bulletin)

    st.subheader("Cảnh báo")
    st.caption("Kiểm tra trên dữ liệu đã lưu khi mở tab hoặc bấm nút. Không gọi API và không chạy nền.")
    if st.button("Kiểm tra lại"):
        st.rerun()
    report = check_alerts()
    if report.empty:
        st.info("Chưa có cảnh báo.")
    else:
        st.dataframe(report, hide_index=True, width="stretch", alt="Kết quả cảnh báo đang lưu")

    with st.form("add_alert"):
        st.markdown("**Thêm cảnh báo**")
        columns = st.columns(3)
        symbol = columns[0].text_input("Mã", value="POW")
        kind = columns[1].selectbox("Loại", list(ALERT_KINDS))
        level = columns[2].number_input("Ngưỡng", min_value=0.0, value=12.0, step=0.1)
        submitted = st.form_submit_button("Lưu cảnh báo")
    if submitted:
        try:
            add_alert(symbol, kind, None if kind not in PRICE_KINDS else float(level))
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()

    saved = list_alerts()
    if not saved.empty:
        choice = st.selectbox(
            "Xóa cảnh báo",
            saved["id"].astype(str) + " · " + saved["Mã"].astype(str) + " · " + saved["Loại"].astype(str),
        )
        if st.button("Xóa cảnh báo đã chọn"):
            delete_alert(choice.split(" · ", maxsplit=1)[0])
            st.rerun()
