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
  /* --- Chống tràn ngang / lệch trái-phải --- */
  *, *::before, *::after { box-sizing: border-box; }
  html, body { overflow-x: hidden !important; max-width: 100%; }
  [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"],
  [data-testid="stAppScrollToBottomContainer"] { overflow-x: clip !important; max-width: 100%; }
  .stMainBlockContainer, .block-container, [data-testid="stVerticalBlock"],
  [data-testid="stElementContainer"], [data-testid="stPlotlyChart"], .js-plotly-plot,
  [data-testid="stMarkdownContainer"], img, iframe, video, canvas, svg { max-width: 100% !important; }
  [data-testid="stHorizontalBlock"], [data-testid="stVerticalBlock"] { min-width: 0 !important; }
  /* iOS tự zoom khi input < 16px rồi giữ zoom: đây là nguyên nhân "lệch phải, mất mép trái" */
  input, textarea, select, [data-baseweb="select"] input, [data-baseweb="select"] div,
  .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input,
  [data-testid="stMultiSelect"] input { font-size: 16px !important; }
  /* Thanh chọn trang: một hàng, vuốt ngang */
  [data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div,
  [data-testid="stButtonGroup"] div:has(> button) {
    flex-wrap: nowrap !important; overflow-x: auto !important; overflow-y: hidden;
    max-width: 100%; scrollbar-width: none; -webkit-overflow-scrolling: touch;
  }
  [data-testid="stButtonGroup"] button {
    flex: 0 0 auto !important; white-space: nowrap !important;
    padding: 0 0.6rem !important; font-size: var(--ds-font-sm) !important;
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
    min-width: 0 !important;
    flex: 1 1 calc(50% - var(--ds-space-2)) !important;
  }
  [data-testid="stMetricValue"] { font-size: var(--ds-font-lg) !important; }
  [data-testid="stExpander"] details summary { min-height: var(--ds-touch); }
  /* Danh mục / Tin tức: bài viết và form gọn hơn */
  .stTextArea textarea { min-height: 90px !important; }
  [data-testid="stMarkdownContainer"] h3 { margin-top: var(--ds-space-2) !important; }
  hr { margin: var(--ds-space-2) 0 !important; }
}
@media (max-width: 480px) {
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 100% !important;
  }
  .ds-keep-row [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 0 !important;
  }
}
/* Ngang trên điện thoại: chiều cao thấp, tận dụng bề ngang */
@media (orientation: landscape) and (max-height: 500px) {
  :root { --ds-chart-h: 340px; --ds-touch: 40px; }
  html, body { overflow-x: hidden !important; max-width: 100%; }
  [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow-x: clip !important; }
  input, textarea, select, [data-baseweb="select"] input, .stTextInput input, .stNumberInput input,
  .stTextArea textarea, .stDateInput input, [data-testid="stMultiSelect"] input { font-size: 16px !important; }
  .stMainBlockContainer, .block-container {
    padding-top: 3.25rem !important;
    padding-left: var(--ds-space-3, 0.75rem) !important;
    padding-right: var(--ds-space-3, 0.75rem) !important;
  }
  h1 { font-size: 1.25rem !important; margin-bottom: 0 !important; }
  h2, h3 { font-size: 1.05rem !important; }
  [data-testid="stForm"] { padding: 0.5rem 0.75rem !important; }
  [data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
  [data-testid="stCaptionContainer"] { font-size: 0.7rem !important; }
  .stTextArea textarea { min-height: 70px !important; }
  /* Sidebar hẹp lại khi xoay ngang để nội dung chính đủ rộng */
  section[data-testid="stSidebar"] {
    width: 220px !important; min-width: 220px !important; max-width: 220px !important;
  }
  section[data-testid="stSidebar"] [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
  /* Thanh phân trang tin: 4 nút một hàng khi xoay ngang */
  .st-key-news_pager [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 0 !important;
  }
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 calc(33% - 0.5rem) !important;
  }
}
/* Biểu đồ: bản mobile (420px, chú thích dưới) cho màn hẹp hoặc xoay ngang thấp; bản desktop giữ nguyên */
@media (max-width: 768px), (orientation: landscape) and (max-height: 500px) {
  [class*="st-key-dschart-d-"] { display: none !important; }
}
@media (min-width: 769px) and (min-height: 501px) {
  [class*="st-key-dschart-m-"] { display: none !important; }
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
