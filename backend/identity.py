"""Authentik identity from ForwardAuth headers (ADR 0003/0006) + desk session cookie (DEV)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

_ME_HEADERS = {
    "username": "x-authentik-username",
    "email": "x-authentik-email",
    "name": "x-authentik-name",
    "uid": "x-authentik-uid",
    "groups": "x-authentik-groups",
}

_DEFAULT_ADMIN_GROUPS = ("admin",)


def username_from_headers(headers: Mapping[str, str] | None) -> str:
    if not headers:
        return "local"
    for key, value in headers.items():
        if str(key).lower() == _ME_HEADERS["username"] and str(value).strip():
            return str(value).strip()
    return "local"


def me_from_headers(headers: Mapping[str, str] | None) -> dict | None:
    """None nếu chưa đăng nhập (thiếu username)."""
    if not headers:
        return None
    lowered = {str(key).lower(): str(value).strip() for key, value in headers.items()}
    me = {field: lowered.get(header, "") for field, header in _ME_HEADERS.items()}
    if not me["username"]:
        return None
    raw_groups = me["groups"]
    me["groups"] = [g.strip() for g in re.split(r"[|,]", raw_groups) if g.strip()]
    return me


def is_admin_user(
    groups: Sequence[str] | None,
    admin_groups: Iterable[str] | None = None,
) -> bool:
    """True nếu user thuộc ít nhất một group admin (case-insensitive)."""
    allowed = {str(g).strip().lower() for g in (admin_groups or _DEFAULT_ADMIN_GROUPS) if str(g).strip()}
    if not allowed:
        return False
    for g in groups or ():
        if str(g).strip().lower() in allowed:
            return True
    return False


def roles_for_user(groups: Sequence[str] | None, *, is_admin: bool) -> list[str]:
    """Role SPA: luôn có ``user``; thêm ``admin`` khi is_admin."""
    roles = ["user"]
    if is_admin:
        roles.append("admin")
    # giữ group gốc như role phụ (không trùng)
    seen = {r.lower() for r in roles}
    for g in groups or ():
        name = str(g).strip()
        if name and name.lower() not in seen:
            roles.append(name)
            seen.add(name.lower())
    return roles


def resolve_me(
    headers: Mapping[str, str] | None,
    *,
    desk_cookie: str | None = None,
    desk_form_mode: bool = False,
) -> dict[str, Any] | None:
    """Resolve identity.

    - ``desk_form_mode=True`` (Unified Login / Desk Session form): **chỉ** cookie
      ``atz_desk_session``. Bỏ qua ForwardAuth headers — tránh cookie Outpost sót
      khiến SPA vẫn “đã login” hoặc đẩy user sang auth.atz.vn.
    - Mặc định (legacy): ForwardAuth trước, fallback desk cookie.
    """
    desk_me: dict[str, Any] | None = None
    try:
        from backend.desk_session import desk_session_enabled, me_from_cookie

        if desk_session_enabled():
            desk_me = me_from_cookie(desk_cookie)
    except Exception:
        desk_me = None

    if desk_form_mode:
        return desk_me

    me = me_from_headers(headers)
    if me:
        me = dict(me)
        me["source"] = "forward_auth"
        return me
    return desk_me


def resolve_request_identity(
    headers: Mapping[str, str] | None,
    *,
    desk_cookie: str | None = None,
) -> dict[str, Any] | None:
    """resolve_me + đọc ``desk_session_form`` từ account config (Unified Login)."""
    desk_form = False
    try:
        from backend.account_config import load_account_config

        desk_form = bool(load_account_config().get("desk_session_form"))
    except Exception:
        desk_form = False
    return resolve_me(
        headers,
        desk_cookie=desk_cookie,
        desk_form_mode=desk_form,
    )
