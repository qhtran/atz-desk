"""Điều hướng trang quét thị trường. Logic lọc và chỉ báo nằm ở analysis/ và datasource/."""

from __future__ import annotations

import warnings

import streamlit as st

from ui.mobile import inject_mobile_css
from ui.pages import open_page

warnings.filterwarnings("ignore", category=UserWarning, module=r"vnstock(\.|$)")


def main() -> None:
    st.set_page_config(page_title="Quét thị trường", layout="wide")
    inject_mobile_css()
    st.title("Quét thị trường")
    st.caption(
        "Top 20 mã lọc theo ROE quý gần nhất và thanh khoản. Bấm «Quét và làm mới dữ liệu» để cập nhật."
    )
    open_page()


if __name__ == "__main__":
    main()
