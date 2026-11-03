"""Authentik identity from ForwardAuth headers (ADR 0003/0006)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

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
