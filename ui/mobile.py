"""CSS cho màn hình hẹp (điện thoại). Desktop không đổi vì mọi luật nằm trong @media."""

from __future__ import annotations

import streamlit as st

_MOBILE_CSS = """
<style>
/* Design system mobile-first. Mọi luật nằm trong @media nên desktop không đổi. */
@media (max-width: 768px) {
  :root {
    --ds-space-1: 0.25rem;
    --ds-space-2: 0.5rem;
    --ds-space-3: 0.75rem;
    --ds-space-4: 1rem;
    --ds-font-xs: 0.72rem;
    --ds-font-sm: 0.8rem;
    --ds-font-md: 0.9rem;
    --ds-font-lg: 1.15rem;
    --ds-font-xl: 1.45rem;
    --ds-touch: 44px;
    --ds-chart-h: 420px;
  }
  .stMainBlockContainer, .block-container {
    padding-left: var(--ds-space-2) !important;
    padding-right: var(--ds-space-2) !important;
    padding-top: 2.5rem !important;
  }
  h1 { font-size: var(--ds-font-xl) !important; }
  h2, h3 { font-size: var(--ds-font-lg) !important; }
  [data-testid="stCaptionContainer"] { font-size: var(--ds-font-xs) !important; }
  /* Touch target tối thiểu 44px */
  .stButton button, .stDownloadButton button, .stFormSubmitButton button,
  .stLinkButton a, [data-testid="stButtonGroup"] button,
  [data-baseweb="select"] > div, [data-baseweb="input"], .stTextInput input,
  .stNumberInput input, .stDateInput input, [data-baseweb="tab"] {
    min-height: var(--ds-touch) !important;
  }
  /* Bảng: lớp dùng chung .ds-table + bảng markdown + dataframe */
  .ds-table, [data-testid="stDataFrame"], [data-testid="stTable"] {
    overflow-x: auto; max-width: 100%;
  }
  [data-testid="stMarkdownContainer"] table, .ds-table table {
    display: block; overflow-x: auto; max-width: 100%;
    white-space: nowrap; font-size: var(--ds-font-sm);
  }
  [data-testid="stMarkdownContainer"] th, [data-testid="stMarkdownContainer"] td,
  .ds-table th, .ds-table td { padding: var(--ds-space-1) var(--ds-space-2) !important; }
  /* Biểu đồ: lớp .ds-chart, giữ full width, không méo */
  .ds-chart, [data-testid="stPlotlyChart"] { width: 100% !important; max-width: 100%; }
  /* Form: input full width, khoảng cách gọn */
  .ds-form, [data-testid="stForm"] { padding: var(--ds-space-3) !important; }
  [data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: var(--ds-space-2) !important; }
  [data-testid="stMultiSelect"], [data-testid="stSelectbox"], [data-testid="stTextInput"] { width: 100% !important; }
  /* Cột wrap 2 cột/hàng */
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: var(--ds-space-2) !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: calc(50% - var(--ds-space-2)) !important;
    flex: 1 1 calc(50% - var(--ds-space-2)) !important;
  }
  [data-testid="stMetricValue"] { font-size: var(--ds-font-lg) !important; }
  [data-testid="stButtonGroup"] { overflow-x: auto; flex-wrap: nowrap; }
  [data-testid="stExpander"] details summary { min-height: var(--ds-touch); }
}
@media (max-width: 480px) {
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 100% !important; flex: 1 1 100% !important;
  }
  .ds-keep-row [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 0 !important;
  }
}
/* Ngang trên điện thoại: chiều cao thấp, tận dụng bề ngang */
@media (orientation: landscape) and (max-height: 500px) {
  :root { --ds-chart-h: 340px; --ds-touch: 40px; }
  .stMainBlockContainer, .block-container {
    padding-top: 1.5rem !important;
    padding-left: var(--ds-space-3, 0.75rem) !important;
    padding-right: var(--ds-space-3, 0.75rem) !important;
  }
  h1 { font-size: 1.25rem !important; margin-bottom: 0 !important; }
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: calc(33% - 0.5rem) !important; flex: 1 1 calc(33% - 0.5rem) !important;
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
