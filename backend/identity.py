"""Authentik identity from ForwardAuth headers."""

from __future__ import annotations

import re
from collections.abc import Mapping

_ME_HEADERS = {
    "username": "x-authentik-username",
    "email": "x-authentik-email",
    "name": "x-authentik-name",
    "uid": "x-authentik-uid",
    "groups": "x-authentik-groups",
}


def username_from_headers(headers: Mapping[str, str] | None) -> str:
    if not headers:
        return "local"
    for key, value in headers.items():
        if str(key).lower() == _ME_HEADERS["username"] and str(value).strip():
            return str(value).strip()
    return "local"


def me_from_headers(headers: Mapping[str, str] | None) -> dict | None:
    if not headers:
        return None
    lowered = {str(key).lower(): str(value).strip() for key, value in headers.items()}
    me = {field: lowered.get(header, "") for field, header in _ME_HEADERS.items()}
    if not me["username"]:
        return None
    raw_groups = me["groups"]
    me["groups"] = [g.strip() for g in re.split(r"[|,]", raw_groups) if g.strip()]
    return me
