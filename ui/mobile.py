"""CSS cho màn hình hẹp (điện thoại). Desktop không đổi vì mọi luật nằm trong @media."""

from __future__ import annotations

import streamlit as st

_MOBILE_CSS = """
<style>
@media (max-width: 768px) {
  /* Bớt lề khối chính để bảng có thêm chỗ */
  .stMainBlockContainer, .block-container {
    padding-left: 0.6rem !important;
    padding-right: 0.6rem !important;
    padding-top: 2.5rem !important;
  }
  h1 { font-size: 1.5rem !important; }
  h2, h3 { font-size: 1.15rem !important; }
  /* Bảng markdown/HTML (vd. bản tin) cuộn ngang thay vì tràn màn hình */
  [data-testid="stMarkdownContainer"] table {
    display: block;
    overflow-x: auto;
    max-width: 100%;
    white-space: nowrap;
    font-size: 0.8rem;
  }
  [data-testid="stMarkdownContainer"] th,
  [data-testid="stMarkdownContainer"] td { padding: 0.25rem 0.4rem !important; }
  [data-testid="stTable"], [data-testid="stDataFrame"] {
    overflow-x: auto;
    max-width: 100%;
  }
  [data-testid="stTable"] table { font-size: 0.8rem; }
  /* Cột cho phép xuống dòng khi hẹp */
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 0.5rem !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: calc(50% - 0.5rem) !important;
    flex: 1 1 calc(50% - 0.5rem) !important;
  }
  [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
  /* Thanh chọn trang cuộn ngang thay vì bị cắt */
  [data-testid="stButtonGroup"] { overflow-x: auto; flex-wrap: nowrap; }
}
@media (max-width: 480px) {
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }
}
</style>
"""


def inject_mobile_css() -> None:
    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)


def pinned(*names: str) -> dict:
    """column_config ghim các cột đầu (vd. «Mã») khi cuộn ngang."""
    try:
        return {name: st.column_config.Column(pinned=True) for name in names}
    except TypeError:
        return {}
