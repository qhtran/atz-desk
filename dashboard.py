"""Dashboard: trạng thái phiên và Top 20. Trang một mã nằm ở app.py."""

from __future__ import annotations

import warnings

import streamlit as st

from datasource.cache import read_cache
from ui.pages import show_dashboard

warnings.filterwarnings("ignore", category=UserWarning, module=r"vnstock(\.|$)")


def main() -> None:
    st.set_page_config(page_title="Tổng quan", layout="wide")
    st.title("Tổng quan")
    st.caption("Trạng thái phiên HOSE và Top 20 đã lọc. Biểu đồ từng mã nằm ở trang Quét thị trường.")
    try:
        board = read_cache()
    except Exception as error:
        st.error(f"Không đọc được Top 20 đã lưu: {error}")
        return
    show_dashboard(board)


if __name__ == "__main__":
    main()
