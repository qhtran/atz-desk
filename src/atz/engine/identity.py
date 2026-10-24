"""Chọn username. Nguồn hiện tại là header Authentik hoặc tên local."""

from __future__ import annotations

import re
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



# Header nginx chuyển từ outpost Authentik (deploy/authentik/nginx/atz.vn.conf).
_ME_HEADERS = {
    "username": "x-authentik-username",
    "email": "x-authentik-email",
    "name": "x-authentik-name",
    "uid": "x-authentik-uid",
    "groups": "x-authentik-groups",
}


def me_from_headers(headers: Mapping[str, str] | None) -> dict | None:
    """Gom header X-authentik-* thành dict `me`. Không có username thì trả None (chưa đăng nhập).

    Authentik gửi groups dạng "a|b|c". Hàm không đọc Streamlit và không gọi mạng.
    """
    if not headers:
        return None
    lowered = {str(key).lower(): str(value).strip() for key, value in headers.items()}
    me = {field: lowered.get(header, "") for field, header in _ME_HEADERS.items()}
    if not me["username"]:
        return None
    raw_groups = me["groups"]
    me["groups"] = [group.strip() for group in re.split(r"[|,]", raw_groups) if group.strip()]
    return me


def current_me() -> dict | None:
    """Đọc `me` từ header Authentik qua Streamlit. Không có header thì None."""
    try:
        import streamlit as st

        headers = dict(st.context.headers)
    except Exception:
        headers = None
    return me_from_headers(headers)
