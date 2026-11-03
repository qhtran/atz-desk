"""Signed HttpOnly desk session cookie (DEV headless auth) — không thay Outpost cookie."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any

COOKIE_NAME = "atz_desk_session"
DEFAULT_TTL_SEC = 12 * 3600


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def session_secret() -> str:
    return (os.getenv("DESK_SESSION_SECRET") or "").strip()


def desk_session_enabled() -> bool:
    """Bật khi DESK_SESSION_AUTH=1 (hoặc true) — mặc định tắt nếu thiếu secret."""
    flag = (os.getenv("DESK_SESSION_AUTH") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return bool(session_secret())
    # auto: bật nếu có secret (dev compose nên set cả hai)
    return bool(session_secret())


def issue_session_value(
    *,
    username: str,
    email: str = "",
    name: str = "",
    uid: str = "",
    groups: list[str] | None = None,
    ttl_sec: int | None = None,
    is_superuser: bool = False,
) -> str:
    secret = session_secret()
    if not secret:
        raise RuntimeError("DESK_SESSION_SECRET missing")
    now = int(time.time())
    ttl = int(ttl_sec or os.getenv("DESK_SESSION_TTL_SEC") or DEFAULT_TTL_SEC)
    payload = {
        "u": str(username).strip(),
        "e": str(email or "").strip(),
        "n": str(name or "").strip(),
        "id": str(uid or "").strip(),
        "g": [str(g).strip() for g in (groups or []) if str(g).strip()],
        "su": bool(is_superuser),
        "iat": now,
        "exp": now + max(300, ttl),
    }
    if not payload["u"]:
        raise ValueError("username required")
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _b64url_encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_session_value(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    secret = session_secret()
    if not secret:
        return None
    body, _, sig = token.partition(".")
    if not body or not sig:
        return None
    expect = _b64url_encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = int(payload.get("exp") or 0)
    if exp < int(time.time()):
        return None
    username = str(payload.get("u") or "").strip()
    if not username:
        return None
    groups = payload.get("g") if isinstance(payload.get("g"), list) else []
    return {
        "username": username,
        "email": str(payload.get("e") or ""),
        "name": str(payload.get("n") or ""),
        "uid": str(payload.get("id") or ""),
        "groups": [str(g).strip() for g in groups if str(g).strip()],
        "is_superuser": bool(payload.get("su")),
        "source": "desk_session",
    }


def me_from_cookie(cookie_header_value: str | None) -> dict[str, Any] | None:
    return verify_session_value(cookie_header_value)
