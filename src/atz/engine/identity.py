"""Chọn username. Nguồn hiện tại là header Authentik hoặc tên local."""

from __future__ import annotations

from collections.abc import Mapping

_HEADER = "x-authentik-username"


def username_from_headers(headers: Mapping[str, str] | None) -> str:
    """Đọc X-authentik-username. Không có header hoặc header rỗng thì trả 'local'.

    Hàm không đọc Streamlit. Khi đổi cách đăng nhập, chỉ chỗ gọi hàm này cần sửa.
    """
    if not headers:
        return "local"
    for key, value in headers.items():
        if key.lower() == _HEADER and str(value).strip():
            return str(value).strip()
    return "local"


def current_username() -> str:
    """Đọc username từ header Authentik qua Streamlit. Không có thì 'local'."""
    try:
        import streamlit as st

        headers = dict(st.context.headers)
    except Exception:
        headers = None
    return username_from_headers(headers)

