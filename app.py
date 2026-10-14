"""Điều hướng trang quét thị trường. Logic lọc và chỉ báo nằm ở analysis/ và datasource/."""

from __future__ import annotations

import warnings

import streamlit as st

from ui.pages import open_page

warnings.filterwarnings("ignore", category=UserWarning, module=r"vnstock(\.|$)")


def main() -> None:
    st.set_page_config(page_title="Quét thị trường", layout="wide")
    st.title("Quét thị trường")
    st.caption(
        "Bảng Top 20 đọc từ top20_cache.csv. "
        "Lần quét lấy giá (KBS) và ROE quý mới nhất song song, rồi lọc ROE và thanh khoản."
    )
    open_page()


if __name__ == "__main__":
    main()
